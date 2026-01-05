import json
import logging
import backend.core.llm as llm
from typing import List, Dict, Any, Tuple
from backend.core.local_ml import (
    batch_validate_locally,
    remove_duplicate_questions,
    is_local_ml_available
)

logger = logging.getLogger(__name__)

class QuestionValidator:
    def __init__(self):
        pass

    def validate_question_batch_stream(self, questions: List[Dict[str, Any]], topic: str, content: str = "", skip_api: bool = False):
        """
        Validates a batch of questions with streaming support.
        Yields validation thinking chunks, then returns the final validated questions.
        
        If skip_api=True, only performs local validation (no Gemini API call).
        """
        if not questions:
            yield None, []
            return

        logger.info(f"Validating batch of {len(questions)} questions for topic: {topic}")
        
        # Step 1: Local pre-validation (catches obvious issues without API)
        if is_local_ml_available():
            yield "🔍 Running local validation checks...\n", None
            valid_questions, issues = batch_validate_locally(questions)
            
            if issues:
                yield f"⚠️ Found {len(issues)} issues locally:\n" + "\n".join(issues[:5]) + "\n", None
            
            # Remove duplicates locally
            original_count = len(valid_questions)
            valid_questions = remove_duplicate_questions(valid_questions)
            if len(valid_questions) < original_count:
                yield f"🔄 Removed {original_count - len(valid_questions)} duplicate questions\n", None
            
            questions = valid_questions
            
            if not questions:
                yield "❌ No valid questions after local validation\n", []
                return
            
            yield f"✅ {len(questions)} questions passed local validation\n", None
        
        # Step 2: If skip_api is True, return after local validation
        if skip_api:
            yield None, questions
            return
        
        # First, ask LLM to validate and explain its validation process
        validation_prompt = f"""
You are an expert academic editor and fact-checker.
Your task is to validate the following Multiple Choice Questions (MCQs) on the topic: "{topic}".

Context provided to the generator:
{content[:500] if content else 'General knowledge'}

Input Questions (JSON):
{json.dumps(questions, indent=2)}

Validate each question by checking:
1. **Relevance**: Is the question strictly related to the topic?
2. **Correctness**: Is the 'answer' field definitely correct?
3. **Clarity**: Is the question phrased clearly?
4. **Options Quality**: Are all options plausible but only one correct?

For each question, provide detailed analysis:
- State the question number
- Evaluate relevance, correctness, clarity, and options
- Note any issues found
- Recommend whether to KEEP, FIX, or REMOVE

Format your validation as a detailed report, examining each question systematically.
"""

        try:
            # Get validation thinking (non-JSON, natural language)
            response = llm.model.generate_content(
                validation_prompt,
                stream=True
            )

            validation_thinking = ""
            for chunk in response:
                if chunk.text:
                    validation_thinking += chunk.text
                    yield chunk.text, None

            logger.info("Validation thinking captured, now applying fixes...")

            # Now use the validation thinking to generate corrected questions
            correction_prompt = f"""
Based on the validation analysis, here are the original questions:

{json.dumps(questions, indent=2)}

Apply the necessary corrections:
- Keep valid questions as is
- Fix minor errors (typos, wrong answer key if obvious)
- Remove or replace completely incorrect questions

Return ONLY the corrected JSON array of questions.
"""

            generation_config = llm.get_generation_config_json(llm.questions_schema)
            
            correction_response = llm.model.generate_content(
                correction_prompt,
                generation_config=generation_config
            )

            if not correction_response.text:
                logger.warning("Correction returned empty response. Returning original questions.")
                yield None, questions
                return

            validated_data = json.loads(correction_response.text)
            
            if isinstance(validated_data, list):
                logger.info(f"Validation complete. Input: {len(questions)}, Output: {len(validated_data)}")
                yield None, validated_data
            else:
                logger.warning("Validator output format incorrect. Returning original questions.")
                yield None, questions

        except Exception as e:
            logger.error(f"Error during validation: {e}")
            yield None, questions

    def validate_question_batch(self, questions: List[Dict[str, Any]], topic: str, content: str = "") -> List[Dict[str, Any]]:
        """
        Validates a batch of questions for correctness and relevance.
        Returns the validated (and potentially fixed) questions.
        """
        if not questions:
            return []

        logger.info(f"Validating batch of {len(questions)} questions for topic: {topic}")
        
        # We process in batches to save round trips, but small enough to fit context
        # For simplicity, let's validate the whole set if it's small (<= 10), otherwise chunk.
        
        validated_questions = []
        
        prompt = f"""
        You are an expert academic editor and fact-checker.
        Your task is to validate the following list of Multiple Choice Questions (MCQs) on the topic: "{topic}".
        
        Context provided to the generator was:
        {content[:500]}... (truncated)

        Input Questions (JSON):
        {json.dumps(questions)}

        Check for:
        1. **Relevance**: Is the question strictly related to the topic/content?
        2. **Correctness**: Is the 'answer' field definitely correct based on the options?
        3. **Clarity**: Is the question phrased clearly?
        4. **Format**: Does it match the required JSON structure?

        Action:
        - If a question is VALID, keep it as is.
        - If a question has a minor error (typo, wrong answer key but obvious correct option), FIX IT.
        - If a question is completely wrong, irrelevant, or hallucinates facts not in the context, REMOVE IT or REPLACE it with a correct one.

        Output:
        Return ONLY the corrected JSON list of questions. Do not wrap in markdown code blocks.
        """

        try:
            # We reuse the questions_schema to ensure the output structure is maintained
            generation_config = llm.get_generation_config_json(llm.questions_schema)
            
            response = llm.model.generate_content(
                prompt,
                generation_config=generation_config
            )

            if not response.text:
                logger.warning("Validator returned empty response. Returning original questions.")
                return questions

            validated_data = json.loads(response.text)
            
            if isinstance(validated_data, list):
                logger.info(f"Validation complete. Input: {len(questions)}, Output: {len(validated_data)}")
                return validated_data
            else:
                logger.warning("Validator output format incorrect. Returning original questions.")
                return questions

        except Exception as e:
            logger.error(f"Error during validation: {e}")
            return questions
