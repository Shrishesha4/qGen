import json
import logging
from typing import List, Optional, Generator, Any
from sqlalchemy.orm import Session
import backend.core.llm as llm
from backend.services.validator import QuestionValidator
from backend.core.models import QuestionSet, Question, User, GenerationSession

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QuestionGenerator:
    def __init__(self):
        """
        Initialize the QuestionGenerator.
        """
        self.validator = QuestionValidator()

    def generate_questions(
        self,
        topic: str,
        content: Optional[str] = None,
        num_questions: int = 5,
        difficulty: str = "medium",
        question_type: str = "multiple_choice",
        user_context: Optional[str] = None
    ) -> List[dict]:
        """
        Generates questions based on a topic or provided content.
        Chunks requests if num_questions > 25.
        """
        all_questions = []
        chunk_size = 25
        remaining = num_questions

        while remaining > 0:
            current_batch_size = min(remaining, chunk_size)
            logger.info(f"Generating chunk of {current_batch_size} questions (Remaining: {remaining})")
            
            batch_questions = self._generate_single_batch(
                topic, content, current_batch_size, difficulty, question_type, user_context
            )
            
            if batch_questions:
                all_questions.extend(batch_questions)
            
            remaining -= current_batch_size
        
        return all_questions

    def _generate_single_batch(
        self,
        topic: str,
        content: Optional[str],
        num_questions: int,
        difficulty: str,
        question_type: str,
        user_context: Optional[str]
    ) -> List[dict]:
        logger.info(f"Generating {num_questions} {difficulty} {question_type} questions for topic: '{topic}'")

        context_instruction = ""
        if content:
            context_instruction = f"Base your questions STRICTLY on the following content:\n---\n{content}\n---\n"
        else:
            context_instruction = f"Generate questions based on general knowledge of the topic: '{topic}'."

        user_instruction = ""
        if user_context:
            user_instruction = f"User Specific Instructions:\n{user_context}\n"

        prompt = f"""
        You are an expert educational content generator.
        Task: Create a question bank.

        Parameters:
        - Topic: {topic}
        - Quantity: {num_questions}
        - Difficulty: {difficulty}
        - Type: {question_type}

        Instructions:
        {context_instruction}
        {user_instruction}
        1. Ensure questions are accurate, relevant, and grammatically correct.
        2. Provide clear and distinct options for multiple choice questions.
        3. The 'answer' field must be the exact string text of the correct option.
        4. Provide a helpful 'explanation' for why the answer is correct.
        5. Output MUST be a valid JSON array matching the specified schema.
        6. Create UNIQUE questions. Do not repeat questions if called multiple times in a sequence.
        """

        try:
            generation_config = llm.get_generation_config_json(llm.questions_schema)
            
            response = llm.model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            if not response.text:
                logger.error("Received empty response from LLM.")
                return []

            questions_data = json.loads(response.text)
            
            if isinstance(questions_data, list):
                logger.info(f"Successfully generated {len(questions_data)} questions.")
                return questions_data
            else:
                logger.warning("LLM response was not a list as expected.")
                return []

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON response: {e}")
            logger.debug(f"Raw response: {response.text}")
            return []
        except Exception as e:
            logger.error(f"Error generating questions: {e}")
            return []

    def generate_batch_stream(
        self,
        num_sets: int,
        topic: str,
        content: Optional[str] = None,
        num_questions: int = 5,
        difficulty: str = "medium",
        question_type: str = "multiple_choice",
        user_context: Optional[str] = None,
        db: Session = None,
        user: User = None,
        session: GenerationSession = None
    ) -> Generator[str, None, None]:
        """
        Generates multiple sets (question banks) of questions, yielding progress updates and results.
        Yields JSON strings formatted as Server-Sent Events (SSE).
        Saves results to DB if db and user are provided.
        Updates session progress if session is provided.
        """
        yield f"data: {json.dumps({'type': 'start', 'total_sets': num_sets})}\n\n"

        for i in range(num_sets):
            current_set = i + 1
            
            # Update session progress
            if session and db:
                progress = int((i / num_sets) * 100)
                session.progress = progress
                session.current_step = f"Generating set {current_set}/{num_sets}"
                db.commit()
            
            # 1. Generate with streaming
            yield f"data: {json.dumps({'type': 'progress', 'message': f'Generating set {current_set}/{num_sets}...', 'step': 'generating', 'set_index': current_set})}\n\n"
            
            # Stream the actual LLM response
            context_instruction = ""
            if content:
                context_instruction = f"Base your questions STRICTLY on the following content:\n---\n{content}\n---\n"
            else:
                context_instruction = f"Generate questions based on general knowledge of the topic: '{topic}'."

            user_instruction = ""
            if user_context:
                user_instruction = f"User Specific Instructions:\n{user_context}\n"

            prompt = f"""
            You are an expert educational content generator.
            Task: Create a question bank.

            Parameters:
            - Topic: {topic}
            - Quantity: {num_questions}
            - Difficulty: {difficulty}
            - Type: {question_type}

            Instructions:
            {context_instruction}
            {user_instruction}
            1. Ensure questions are accurate, relevant, and grammatically correct.
            2. Provide clear and distinct options for multiple choice questions.
            3. The 'answer' field must be the exact string text of the correct option.
            4. Provide a helpful 'explanation' for why the answer is correct.
            5. Output MUST be a valid JSON array matching the specified schema.
            6. Create UNIQUE questions. Do not repeat questions if called multiple times in a sequence.
            """

            try:
                generation_config = llm.get_generation_config_json(llm.questions_schema)
                
                # Use streaming response
                response = llm.model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    stream=True
                )
                
                full_text = ""
                for chunk in response:
                    if chunk.text:
                        full_text += chunk.text
                        # Stream the thinking text to frontend
                        yield f"data: {json.dumps({'type': 'thinking', 'text': chunk.text, 'set_index': current_set})}\n\n"
                
                if not full_text:
                    yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to generate questions for set {current_set}'})}\n\n"
                    continue

                questions = json.loads(full_text)
                
            except Exception as e:
                logger.error(f"Error generating questions: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': f'Failed to generate questions for set {current_set}: {str(e)}'})}\n\n"
                continue

            # 2. Validate
            yield f"data: {json.dumps({'type': 'progress', 'message': f'Validating set {current_set}/{num_sets}...', 'step': 'validating', 'set_index': current_set})}\n\n"

            validated_questions = None
            validation_text = ""
            for chunk_text, result in self.validator.validate_question_batch_stream(
                questions, topic, content if content else ""
            ):
                if chunk_text:
                    # Stream validation thinking
                    validation_text += chunk_text
                    yield f"data: {json.dumps({'type': 'validating', 'text': chunk_text, 'set_index': current_set})}\n\n"
                if result is not None:
                    validated_questions = result

            if validated_questions is None:
                validated_questions = questions

            # 3. Save to DB
            if db and user:
                try:
                    db_set = QuestionSet(
                        topic=topic,
                        difficulty=difficulty,
                        question_type=question_type,
                        validation_text=validation_text,
                        question_count=len(validated_questions),
                        owner_id=user.id,
                        session_id=session.id if session else None
                    )
                    db.add(db_set)
                    db.commit()
                    db.refresh(db_set)

                    db_questions = []
                    for idx, q_data in enumerate(validated_questions):
                        db_q = Question(
                            description=q_data.get("description"),
                            options=q_data.get("options", []),
                            answer=q_data.get("answer"),
                            explanation=q_data.get("explanation"),
                            question_set_id=db_set.id,
                            order_index=idx
                        )
                        db.add(db_q)
                        db_questions.append(db_q)
                    db.commit()
                    
                    # Refresh each question to get auto-generated IDs and add to response
                    for idx, db_q in enumerate(db_questions):
                        db.refresh(db_q)
                        validated_questions[idx]["id"] = db_q.id
                        validated_questions[idx]["set_id"] = db_set.id

                except Exception as e:
                    logger.error(f"Error saving to DB: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Error saving results to database.'})}\n\n"

            # 4. Emit Result
            yield f"data: {json.dumps({'type': 'result', 'set_index': current_set, 'data': validated_questions})}\n\n"
        
        yield f"data: {json.dumps({'type': 'complete'})}\n\n"