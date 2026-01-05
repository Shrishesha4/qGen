"""
Local ML Module - Reduces reliance on Gemini API
Uses sentence-transformers for semantic similarity, duplicate detection, and caching.
"""

import os
import json
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Lazy loading to avoid import overhead if not used
_model = None
_cache_dir = Path("./data/embeddings_cache")


def get_model():
    """Lazy load the sentence-transformers model."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Use a lightweight model (only ~80MB) - good balance of speed/quality
            model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
            logger.info(f"Loading embedding model: {model_name}")
            _model = SentenceTransformer(model_name)
            logger.info("Embedding model loaded successfully")
        except ImportError:
            logger.warning("sentence-transformers not installed. Local ML features disabled.")
            return None
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            return None
    return _model


def compute_embedding(text: str) -> Optional[List[float]]:
    """Compute embedding vector for a text string."""
    model = get_model()
    if model is None:
        return None
    try:
        embedding = model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    except Exception as e:
        logger.error(f"Error computing embedding: {e}")
        return None


def compute_similarity(text1: str, text2: str) -> float:
    """
    Compute semantic similarity between two texts.
    Returns a score between 0 (dissimilar) and 1 (identical).
    """
    model = get_model()
    if model is None:
        return 0.0
    try:
        embeddings = model.encode([text1, text2], convert_to_numpy=True)
        # Cosine similarity
        from numpy import dot
        from numpy.linalg import norm
        similarity = dot(embeddings[0], embeddings[1]) / (norm(embeddings[0]) * norm(embeddings[1]))
        return float(similarity)
    except Exception as e:
        logger.error(f"Error computing similarity: {e}")
        return 0.0


def find_duplicates(questions: List[Dict[str, Any]], threshold: float = 0.85) -> List[Tuple[int, int, float]]:
    """
    Find duplicate/similar questions in a list.
    Returns list of (index1, index2, similarity_score) for pairs above threshold.
    """
    model = get_model()
    if model is None:
        return []
    
    try:
        # Extract question descriptions
        descriptions = [q.get("description", "") for q in questions]
        embeddings = model.encode(descriptions, convert_to_numpy=True)
        
        duplicates = []
        from numpy import dot
        from numpy.linalg import norm
        
        for i in range(len(embeddings)):
            for j in range(i + 1, len(embeddings)):
                similarity = dot(embeddings[i], embeddings[j]) / (norm(embeddings[i]) * norm(embeddings[j]))
                if similarity >= threshold:
                    duplicates.append((i, j, float(similarity)))
        
        return duplicates
    except Exception as e:
        logger.error(f"Error finding duplicates: {e}")
        return []


def remove_duplicate_questions(questions: List[Dict[str, Any]], threshold: float = 0.85) -> List[Dict[str, Any]]:
    """
    Remove semantically duplicate questions, keeping the first occurrence.
    """
    duplicates = find_duplicates(questions, threshold)
    
    if not duplicates:
        return questions
    
    # Collect indices to remove (keep lower index, remove higher)
    indices_to_remove = set()
    for i, j, score in duplicates:
        indices_to_remove.add(j)
        logger.info(f"Removing duplicate question {j} (similar to {i}, score: {score:.2f})")
    
    return [q for idx, q in enumerate(questions) if idx not in indices_to_remove]


# ============ Question Caching System ============

def _get_cache_key(topic: str, content: str, difficulty: str, question_type: str) -> str:
    """Generate a cache key based on generation parameters."""
    cache_input = f"{topic}:{difficulty}:{question_type}:{content[:500] if content else ''}"
    return hashlib.sha256(cache_input.encode()).hexdigest()[:16]


def _ensure_cache_dir():
    """Ensure cache directory exists."""
    _cache_dir.mkdir(parents=True, exist_ok=True)


def get_cached_questions(
    topic: str,
    content: str = "",
    difficulty: str = "medium",
    question_type: str = "multiple_choice"
) -> Optional[List[Dict[str, Any]]]:
    """
    Retrieve cached questions if available.
    Returns None if no cache hit.
    """
    _ensure_cache_dir()
    cache_key = _get_cache_key(topic, content, difficulty, question_type)
    cache_file = _cache_dir / f"{cache_key}.json"
    
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
                logger.info(f"Cache hit for topic '{topic}' - {len(data['questions'])} questions")
                return data["questions"]
        except Exception as e:
            logger.error(f"Error reading cache: {e}")
    
    return None


def cache_questions(
    questions: List[Dict[str, Any]],
    topic: str,
    content: str = "",
    difficulty: str = "medium",
    question_type: str = "multiple_choice"
):
    """Cache generated questions for future use."""
    _ensure_cache_dir()
    cache_key = _get_cache_key(topic, content, difficulty, question_type)
    cache_file = _cache_dir / f"{cache_key}.json"
    
    try:
        with open(cache_file, "w") as f:
            json.dump({
                "topic": topic,
                "difficulty": difficulty,
                "question_type": question_type,
                "questions": questions
            }, f)
        logger.info(f"Cached {len(questions)} questions for topic '{topic}'")
    except Exception as e:
        logger.error(f"Error writing cache: {e}")


def find_similar_cached_questions(
    topic: str,
    num_questions: int = 5,
    similarity_threshold: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Find questions from cache that are semantically similar to the topic.
    Useful for supplementing API-generated questions.
    """
    _ensure_cache_dir()
    model = get_model()
    
    if model is None:
        return []
    
    all_questions = []
    
    # Load all cached questions
    for cache_file in _cache_dir.glob("*.json"):
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
                for q in data.get("questions", []):
                    q["_source_topic"] = data.get("topic", "unknown")
                    all_questions.append(q)
        except Exception as e:
            logger.warning(f"Error reading cache file {cache_file}: {e}")
    
    if not all_questions:
        return []
    
    try:
        # Compute similarity of each question to the topic
        topic_embedding = model.encode(topic, convert_to_numpy=True)
        question_texts = [q.get("description", "") for q in all_questions]
        question_embeddings = model.encode(question_texts, convert_to_numpy=True)
        
        from numpy import dot
        from numpy.linalg import norm
        
        scored_questions = []
        for idx, q_emb in enumerate(question_embeddings):
            similarity = dot(topic_embedding, q_emb) / (norm(topic_embedding) * norm(q_emb))
            if similarity >= similarity_threshold:
                scored_questions.append((all_questions[idx], float(similarity)))
        
        # Sort by similarity and return top N
        scored_questions.sort(key=lambda x: x[1], reverse=True)
        
        return [q for q, _ in scored_questions[:num_questions]]
    
    except Exception as e:
        logger.error(f"Error finding similar cached questions: {e}")
        return []


# ============ Local Validation (without API) ============

def validate_answer_locally(question: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform basic local validation on a question without using the API.
    Returns validation results.
    """
    results = {
        "is_valid": True,
        "issues": []
    }
    
    description = question.get("description", "")
    options = question.get("options", [])
    answer = question.get("answer", "")
    
    # Check for empty fields
    if not description or len(description) < 10:
        results["issues"].append("Question description is too short or empty")
        results["is_valid"] = False
    
    if len(options) < 2:
        results["issues"].append("Too few options (minimum 2 required)")
        results["is_valid"] = False
    
    if len(options) > 6:
        results["issues"].append("Too many options (maximum 6 recommended)")
    
    # Check if answer is in options
    if answer not in options:
        results["issues"].append(f"Answer '{answer}' not found in options")
        results["is_valid"] = False
    
    # Check for duplicate options
    if len(options) != len(set(options)):
        results["issues"].append("Duplicate options detected")
        results["is_valid"] = False
    
    # Check for very short options (likely incomplete)
    for opt in options:
        if len(opt.strip()) < 1:
            results["issues"].append("Empty or very short option detected")
            results["is_valid"] = False
            break
    
    return results


def batch_validate_locally(questions: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Validate a batch of questions locally.
    Returns (valid_questions, list_of_issues).
    """
    valid_questions = []
    all_issues = []
    
    for idx, q in enumerate(questions):
        validation = validate_answer_locally(q)
        if validation["is_valid"]:
            valid_questions.append(q)
        else:
            all_issues.append(f"Q{idx + 1}: {', '.join(validation['issues'])}")
    
    return valid_questions, all_issues


# ============ Content Summarization (for token reduction) ============

def chunk_content(content: str, max_chunk_size: int = 2000) -> List[str]:
    """
    Split content into semantic chunks for processing.
    Helps reduce API token usage by sending only relevant chunks.
    """
    if len(content) <= max_chunk_size:
        return [content]
    
    # Split by paragraphs first
    paragraphs = content.split("\n\n")
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        if len(current_chunk) + len(para) <= max_chunk_size:
            current_chunk += para + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks


def get_most_relevant_chunk(chunks: List[str], topic: str) -> str:
    """
    Find the most relevant content chunk for a given topic.
    Useful for focusing API calls on relevant content only.
    """
    model = get_model()
    
    if model is None or len(chunks) <= 1:
        return chunks[0] if chunks else ""
    
    try:
        topic_embedding = model.encode(topic, convert_to_numpy=True)
        chunk_embeddings = model.encode(chunks, convert_to_numpy=True)
        
        from numpy import dot
        from numpy.linalg import norm
        
        best_idx = 0
        best_score = -1
        
        for idx, chunk_emb in enumerate(chunk_embeddings):
            similarity = dot(topic_embedding, chunk_emb) / (norm(topic_embedding) * norm(chunk_emb))
            if similarity > best_score:
                best_score = similarity
                best_idx = idx
        
        logger.info(f"Selected chunk {best_idx + 1}/{len(chunks)} with similarity {best_score:.2f}")
        return chunks[best_idx]
    
    except Exception as e:
        logger.error(f"Error finding relevant chunk: {e}")
        return chunks[0] if chunks else ""


# ============ Health Check ============

def is_local_ml_available() -> bool:
    """Check if local ML features are available."""
    return get_model() is not None
