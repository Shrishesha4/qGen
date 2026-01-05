import sys
import os
import csv
import io
import json
import uvicorn
from datetime import timedelta, datetime
from typing import List, Optional, Set
import asyncio
from dotenv import load_dotenv

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(root_dir, '.env'))

sys.path.append(root_dir)

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse, Response, FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from fpdf import FPDF
from pathlib import Path
from typing import Dict, Set
import asyncio

from backend.services.generator import QuestionGenerator
from backend.services.validator import QuestionValidator
from backend.core.pdf_processor import extract_text_from_pdf
from backend.core.database import engine, get_db, Base
from backend.core import models
from backend.services import auth
from backend import schemas

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):

    db = next(get_db())
    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin")
    
    try:
        user = db.query(models.User).filter(models.User.email == admin_email).first()
        if not user:
            hashed_password = auth.get_password_hash(admin_password)
            new_user = models.User(email=admin_email, hashed_password=hashed_password, is_admin=True)
            db.add(new_user)
            db.commit()
            print(f"Admin user created: {admin_email}")
        else:
            # Ensure existing admin has is_admin=True
            if not user.is_admin:
                user.is_admin = True
                db.commit()
            print(f"Admin user exists: {admin_email}")
    except Exception as e:
        print(f"Error seeding admin user: {e}")
    finally:
        db.close()
    
    yield



Base.metadata.create_all(bind=engine)

app = FastAPI(lifespan=lifespan)

# Get CORS origins from environment variable
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# WebSocket connection manager for real-time session updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast_session_update(self, session_data: dict):
        """Broadcast session updates to all connected admin clients"""
        disconnected = set()
        for connection in self.active_connections:
            try:
                await connection.send_json({
                    "type": "session_update",
                    "data": session_data
                })
            except:
                disconnected.add(connection)
        # Clean up disconnected clients
        self.active_connections -= disconnected

manager = ConnectionManager()


# WebSocket endpoint for admin to receive real-time session updates
@app.websocket("/ws/admin/sessions")
async def websocket_admin_sessions(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and wait for messages
            data = await websocket.receive_text()
            # Echo back for ping/pong
            await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/token", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    try:
        user = db.query(models.User).filter(models.User.email == form_data.username).first()
        if not user:
            print(f"User not found: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not auth.verify_password(form_data.password, user.hashed_password):
            print(f"Password verification failed for: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
            
        access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = auth.create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        print(f"Login Error: {e}")
        raise e

@app.get("/users/me", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@app.get("/users", response_model=List[schemas.User])
def get_all_users(current_user: models.User = Depends(auth.get_current_admin), db: Session = Depends(get_db)):
    return db.query(models.User).all()

@app.post("/users", response_model=schemas.User)
def create_user_by_admin(user: schemas.UserCreate, current_user: models.User = Depends(auth.get_current_admin), db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.delete("/users/{user_id}")
def delete_user(user_id: int, current_user: models.User = Depends(auth.get_current_admin), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.email == current_user.email:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}

@app.put("/users/{user_id}/toggle-active")
def toggle_user_active(user_id: int, current_user: models.User = Depends(auth.get_current_admin), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.email == current_user.email:
        raise HTTPException(status_code=400, detail="Cannot block yourself")
    
    user.is_active = not user.is_active
    db.commit()
    return {"message": f"User active status: {user.is_active}"}


@app.get("/api/health")
async def health_check():
    """Health check endpoint for monitoring and load balancers"""
    from backend.core.local_ml import is_local_ml_available
    
    return {
        "status": "healthy",
        "service": "question-bank-generator",
        "timestamp": datetime.utcnow().isoformat(),
        "features": {
            "local_ml": is_local_ml_available(),
            "gemini_api": bool(os.getenv("GEMINI_API_KEY"))
        }
    }


@app.get("/api/features")
async def get_features():
    """Get available features and optimization status"""
    from backend.core.local_ml import is_local_ml_available
    
    return {
        "local_ml": {
            "available": is_local_ml_available(),
            "features": [
                "Semantic duplicate detection",
                "Question caching",
                "Content chunk optimization", 
                "Local pre-validation"
            ] if is_local_ml_available() else []
        },
        "gemini_api": {
            "configured": bool(os.getenv("GEMINI_API_KEY")),
            "features": [
                "Question generation",
                "Advanced validation",
                "Explanation generation"
            ]
        }
    }

@app.post("/generate")
async def generate_questions_endpoint(
    topic: str = Form(...),
    content: Optional[str] = Form(None),
    num_questions: int = Form(5),
    num_sets: int = Form(1),
    difficulty: str = Form("medium"),
    question_type: str = Form("multiple_choice"),
    user_context: Optional[str] = Form(None),
    task_id: Optional[int] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Create a generation session
        session = models.GenerationSession(
            user_id=current_user.id,
            topic=topic,
            num_questions=num_questions,
            num_sets=num_sets,
            difficulty=difficulty,
            question_type=question_type,
            status="active",
            task_id=task_id
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Broadcast new active session to admin clients
        await manager.broadcast_session_update({
            "session_id": session.session_id,
            "user_id": current_user.id,
            "user_email": current_user.email,
            "topic": topic,
            "status": "active",
            "num_questions": num_questions,
            "num_sets": num_sets,
            "difficulty": difficulty,
            "question_type": question_type,
            "started_at": session.started_at.isoformat(),
            "progress": 0
        })

        file_content = ""
        if file:
            if file.content_type == "application/pdf":
                file_bytes = await file.read()
                file_content = extract_text_from_pdf(file_bytes)
            elif file.content_type.startswith("text/"):
                file_bytes = await file.read()
                file_content = file_bytes.decode("utf-8")
        
        full_content = ""
        if content: full_content += content + "\n\n"
        if file_content: full_content += file_content

        async def event_generator():
            try:
                # Send session_id first
                yield f"data: {json.dumps({'type': 'session', 'session_id': session.session_id})}\n\n"
                
                generator = QuestionGenerator()
                for event in generator.generate_batch_stream(
                    topic=topic,
                    content=full_content.strip() if full_content.strip() else None,
                    num_questions=num_questions,
                    num_sets=num_sets,
                    difficulty=difficulty,
                    question_type=question_type,
                    user_context=user_context,
                    db=db,
                    user=current_user,
                    session=session
                ):
                    yield event
                
                # Mark session as completed
                session.status = "completed"
                session.completed_at = datetime.utcnow()
                session.progress = 100
                db.commit()
                
                # Broadcast completion to admin clients
                await manager.broadcast_session_update({
                    "session_id": session.session_id,
                    "user_id": current_user.id,
                    "user_email": current_user.email,
                    "topic": topic,
                    "status": "completed",
                    "completed_at": session.completed_at.isoformat(),
                    "progress": 100
                })
                
                # If this was a task, mark it as completed
                if task_id:
                    task = db.query(models.Task).filter(models.Task.id == task_id).first()
                    if task and task.assignee_id == current_user.id:
                        task.status = "completed"
                        task.completed_at = datetime.utcnow()
                        db.commit()
                
            except Exception as e:
                session.status = "failed"
                session.error_message = str(e)
                db.commit()
                
                # Broadcast failure to admin clients
                await manager.broadcast_session_update({
                    "session_id": session.session_id,
                    "user_id": current_user.id,
                    "user_email": current_user.email,
                    "topic": topic,
                    "status": "failed",
                    "error_message": str(e)
                })
                raise

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history", response_model=List[schemas.QuestionSet])
def get_history(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    return db.query(models.QuestionSet).filter(models.QuestionSet.owner_id == current_user.id).order_by(models.QuestionSet.created_at.desc()).all()

@app.get("/history/{set_id}", response_model=schemas.QuestionSet)
def get_question_set(set_id: int, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    q_set = db.query(models.QuestionSet).filter(models.QuestionSet.id == set_id, models.QuestionSet.owner_id == current_user.id).first()
    if not q_set:
        raise HTTPException(status_code=404, detail="Question set not found")
    return q_set

@app.delete("/history/{set_id}")
def delete_question_set(set_id: int, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)):
    q_set = db.query(models.QuestionSet).filter(models.QuestionSet.id == set_id, models.QuestionSet.owner_id == current_user.id).first()
    if not q_set:
        raise HTTPException(status_code=404, detail="Question set not found")
    
    db.delete(q_set)
    db.commit()
    return {"message": "Question set deleted successfully"}

@app.post("/regenerate/{question_id}")
def regenerate_single_question(
    question_id: int, 
    current_user: models.User = Depends(auth.get_current_user), 
    db: Session = Depends(get_db)
):

    db_question = db.query(models.Question).filter(models.Question.id == question_id).first()
    if not db_question:
        raise HTTPException(status_code=404, detail="Question not found")
    
    q_set = db.query(models.QuestionSet).filter(models.QuestionSet.id == db_question.question_set_id).first()
    if q_set.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    generator = QuestionGenerator()

    new_questions = generator.generate_questions(
        topic=q_set.topic,
        num_questions=1,
        difficulty=q_set.difficulty,
        question_type=q_set.question_type,
        user_context=f"Regenerate a better version of this question: {db_question.description}"
    )

    if not new_questions:
        raise HTTPException(status_code=500, detail="Failed to regenerate")
    
    new_q_data = new_questions[0]

    validator = QuestionValidator()
    validation_text = ""
    validated_data = None
    for chunk_text, result in validator.validate_question_batch_stream(
        [new_q_data], q_set.topic, ""
    ):
        if chunk_text:
            validation_text += chunk_text
        if result is not None:
            validated_data = result
    
    if validated_data:
        new_q_data = validated_data[0]

    db_question.description = new_q_data['description']
    db_question.options = new_q_data['options']
    db_question.answer = new_q_data['answer']
    db_question.explanation = new_q_data.get('explanation', '')

    if q_set.validation_text:
        q_set.validation_text += f"\n\n[Question {question_id} regenerated]\n{validation_text}"
    else:
        q_set.validation_text = f"[Question {question_id} regenerated]\n{validation_text}"
    
    db.commit()
    db.refresh(db_question)

    return db_question

@app.get("/export/{set_id}")
def export_set(
    set_id: int, 
    format: str = "json", 
    current_user: models.User = Depends(auth.get_current_user), 
    db: Session = Depends(get_db)
):
    q_set = db.query(models.QuestionSet).filter(models.QuestionSet.id == set_id, models.QuestionSet.owner_id == current_user.id).first()
    if not q_set:
        raise HTTPException(status_code=404, detail="Question set not found")

    questions = q_set.questions

    if format == "json":
        data = schemas.QuestionSet.from_orm(q_set).json()
        return Response(content=data, media_type="application/json", headers={"Content-Disposition": f"attachment; filename=set_{set_id}.json"})
    
    elif format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Description", "Option A", "Option B", "Option C", "Option D", "Answer", "Explanation"])
        for q in questions:
            options = q.options if q.options else ["", "", "", ""]

            while len(options) < 4: options.append("")
            writer.writerow([q.description, options[0], options[1], options[2], options[3], q.answer, q.explanation])
        return Response(content=output.getvalue(), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename=set_{set_id}.csv"})
    
    elif format == "txt":
        content = f"Topic: {q_set.topic}\n\n"
        for i, q in enumerate(questions):
            content += f"Q{i+1}: {q.description}\n"
            for opt in q.options:
                content += f" - {opt}\n"
            content += f"Answer: {q.answer}\nExplanation: {q.explanation}\n\n"
        return Response(content=content, media_type="text/plain", headers={"Content-Disposition": f"attachment; filename=set_{set_id}.txt"})

    elif format == "pdf":
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Topic: {q_set.topic}", ln=1, align="C")
        pdf.ln(10)
        
        for i, q in enumerate(questions):

            desc = q.description.encode('latin-1', 'replace').decode('latin-1')
            pdf.set_font("Arial", "B", 12)
            pdf.multi_cell(0, 10, txt=f"Q{i+1}: {desc}")
            pdf.set_font("Arial", size=11)
            for opt in q.options:
                opt_txt = opt.encode('latin-1', 'replace').decode('latin-1')
                pdf.cell(0, 8, txt=f"- {opt_txt}", ln=1)
            pdf.ln(2)
            pdf.set_font("Arial", "I", 10)
            ans = q.answer.encode('latin-1', 'replace').decode('latin-1')
            expl = q.explanation.encode('latin-1', 'replace').decode('latin-1') if q.explanation else ""
            pdf.multi_cell(0, 8, txt=f"Ans: {ans} | {expl}")
            pdf.ln(5)
            
        return Response(content=pdf.output(dest='S').encode('latin-1'), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=set_{set_id}.pdf"})

    else:
        raise HTTPException(status_code=400, detail="Invalid format")


# ==================== ADMIN DASHBOARD ENDPOINTS ====================

@app.get("/admin/dashboard", response_model=schemas.AdminDashboardStats)
def get_admin_dashboard(
    current_user: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    total_users = db.query(models.User).count()
    active_users = db.query(models.User).filter(models.User.is_active == True).count()
    total_generations = db.query(models.QuestionSet).count()
    total_questions = db.query(models.Question).count()
    active_sessions = db.query(models.GenerationSession).filter(
        models.GenerationSession.status == "active"
    ).count()
    pending_tasks = db.query(models.Task).filter(
        models.Task.status == "pending"
    ).count()
    
    return schemas.AdminDashboardStats(
        total_users=total_users,
        active_users=active_users,
        total_generations=total_generations,
        total_questions=total_questions,
        active_sessions=active_sessions,
        pending_tasks=pending_tasks
    )

@app.get("/admin/users-with-stats", response_model=List[schemas.UserWithStats])
def get_users_with_stats(
    current_user: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    users = db.query(models.User).all()
    result = []
    for user in users:
        total_generations = db.query(models.QuestionSet).filter(
            models.QuestionSet.owner_id == user.id
        ).count()
        total_questions = db.query(models.Question).join(models.QuestionSet).filter(
            models.QuestionSet.owner_id == user.id
        ).count()
        active_sessions = db.query(models.GenerationSession).filter(
            models.GenerationSession.user_id == user.id,
            models.GenerationSession.status == "active"
        ).count()
        pending_tasks = db.query(models.Task).filter(
            models.Task.assignee_id == user.id,
            models.Task.status == "pending"
        ).count()
        
        result.append(schemas.UserWithStats(
            id=user.id,
            email=user.email,
            is_active=user.is_active,
            is_admin=user.is_admin,
            created_at=user.created_at,
            total_generations=total_generations,
            total_questions=total_questions,
            active_sessions=active_sessions,
            pending_tasks=pending_tasks
        ))
    return result

@app.get("/admin/recent-generations", response_model=List[schemas.QuestionSetWithOwner])
def get_all_recent_generations(
    limit: int = 20,
    current_user: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    sets = db.query(models.QuestionSet).order_by(
        models.QuestionSet.created_at.desc()
    ).limit(limit).all()
    
    result = []
    for s in sets:
        owner = db.query(models.User).filter(models.User.id == s.owner_id).first()
        result.append(schemas.QuestionSetWithOwner(
            id=s.id,
            topic=s.topic,
            difficulty=s.difficulty,
            created_at=s.created_at,
            updated_at=s.updated_at,
            validation_text=s.validation_text,
            question_count=s.question_count,
            is_archived=s.is_archived,
            session_id=s.session_id,
            questions=[],  # Don't include questions in list view
            owner_id=s.owner_id,
            owner_email=owner.email if owner else "Unknown"
        ))
    return result

@app.get("/admin/history", response_model=List[schemas.QuestionSetWithOwner])
def get_all_history(
    current_user: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    """Get all question sets from all users for admin"""
    sets = db.query(models.QuestionSet).order_by(
        models.QuestionSet.created_at.desc()
    ).all()
    
    result = []
    for s in sets:
        owner = db.query(models.User).filter(models.User.id == s.owner_id).first()
        result.append(schemas.QuestionSetWithOwner(
            id=s.id,
            topic=s.topic,
            difficulty=s.difficulty,
            created_at=s.created_at,
            updated_at=s.updated_at,
            validation_text=s.validation_text,
            question_count=s.question_count,
            is_archived=s.is_archived,
            session_id=s.session_id,
            questions=[],
            owner_id=s.owner_id,
            owner_email=owner.email if owner else "Unknown"
        ))
    return result

@app.get("/admin/history/{set_id}", response_model=schemas.QuestionSetWithOwner)
def get_question_set_admin(
    set_id: int,
    current_user: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    """Get question set details for admin (any user's set)"""
    q_set = db.query(models.QuestionSet).filter(models.QuestionSet.id == set_id).first()
    if not q_set:
        raise HTTPException(status_code=404, detail="Question set not found")
    
    owner = db.query(models.User).filter(models.User.id == q_set.owner_id).first()
    return schemas.QuestionSetWithOwner(
        id=q_set.id,
        topic=q_set.topic,
        difficulty=q_set.difficulty,
        created_at=q_set.created_at,
        updated_at=q_set.updated_at,
        validation_text=q_set.validation_text,
        question_count=q_set.question_count,
        is_archived=q_set.is_archived,
        session_id=q_set.session_id,
        questions=q_set.questions,
        owner_id=q_set.owner_id,
        owner_email=owner.email if owner else "Unknown"
    )

@app.delete("/admin/history/{set_id}")
def delete_question_set_admin(
    set_id: int,
    current_user: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete any question set as admin"""
    q_set = db.query(models.QuestionSet).filter(models.QuestionSet.id == set_id).first()
    if not q_set:
        raise HTTPException(status_code=404, detail="Question set not found")
    
    db.delete(q_set)
    db.commit()
    return {"message": "Question set deleted successfully"}

@app.get("/admin/active-sessions", response_model=List[schemas.SessionWithUser])
def get_active_sessions(
    current_user: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    sessions = db.query(models.GenerationSession).filter(
        models.GenerationSession.status == "active"
    ).order_by(models.GenerationSession.started_at.desc()).all()
    
    result = []
    for s in sessions:
        user = db.query(models.User).filter(models.User.id == s.user_id).first()
        result.append(schemas.SessionWithUser(
            id=s.id,
            session_id=s.session_id,
            user_id=s.user_id,
            topic=s.topic,
            num_questions=s.num_questions,
            num_sets=s.num_sets,
            difficulty=s.difficulty,
            question_type=s.question_type,
            status=s.status,
            progress=s.progress,
            current_step=s.current_step,
            error_message=s.error_message,
            started_at=s.started_at,
            completed_at=s.completed_at,
            task_id=s.task_id,
            user_email=user.email if user else "Unknown"
        ))
    return result


# ==================== TASK ENDPOINTS ====================

@app.post("/tasks", response_model=schemas.Task)
def create_task(
    task: schemas.TaskCreate,
    current_user: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    # Verify assignee exists
    assignee = db.query(models.User).filter(models.User.id == task.assignee_id).first()
    if not assignee:
        raise HTTPException(status_code=404, detail="Assignee not found")
    
    db_task = models.Task(
        title=task.title,
        description=task.description,
        topic=task.topic,
        num_questions=task.num_questions,
        num_sets=task.num_sets,
        difficulty=task.difficulty,
        question_type=task.question_type,
        user_context=task.user_context,
        due_date=task.due_date,
        assignee_id=task.assignee_id,
        created_by_id=current_user.id
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@app.get("/tasks", response_model=List[schemas.TaskWithUsers])
def get_all_tasks(
    status: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    query = db.query(models.Task)
    if status:
        query = query.filter(models.Task.status == status)
    tasks = query.order_by(models.Task.created_at.desc()).all()
    
    result = []
    for t in tasks:
        assignee = db.query(models.User).filter(models.User.id == t.assignee_id).first()
        creator = db.query(models.User).filter(models.User.id == t.created_by_id).first()
        result.append(schemas.TaskWithUsers(
            id=t.id,
            title=t.title,
            description=t.description,
            topic=t.topic,
            num_questions=t.num_questions,
            num_sets=t.num_sets,
            difficulty=t.difficulty,
            question_type=t.question_type,
            user_context=t.user_context,
            due_date=t.due_date,
            status=t.status,
            assignee_id=t.assignee_id,
            created_by_id=t.created_by_id,
            created_at=t.created_at,
            completed_at=t.completed_at,
            assignee_email=assignee.email if assignee else "Unknown",
            created_by_email=creator.email if creator else "Unknown"
        ))
    return result

@app.get("/tasks/my", response_model=List[schemas.Task])
def get_my_tasks(
    status: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.Task).filter(models.Task.assignee_id == current_user.id)
    if status:
        query = query.filter(models.Task.status == status)
    return query.order_by(models.Task.created_at.desc()).all()

@app.get("/tasks/{task_id}", response_model=schemas.TaskWithUsers)
def get_task(
    task_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Users can only see their own tasks, admins can see all
    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
    if task.assignee_id != current_user.id and current_user.email != admin_email:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    assignee = db.query(models.User).filter(models.User.id == task.assignee_id).first()
    creator = db.query(models.User).filter(models.User.id == task.created_by_id).first()
    
    return schemas.TaskWithUsers(
        id=task.id,
        title=task.title,
        description=task.description,
        topic=task.topic,
        num_questions=task.num_questions,
        num_sets=task.num_sets,
        difficulty=task.difficulty,
        question_type=task.question_type,
        user_context=task.user_context,
        due_date=task.due_date,
        status=task.status,
        assignee_id=task.assignee_id,
        created_by_id=task.created_by_id,
        created_at=task.created_at,
        completed_at=task.completed_at,
        assignee_email=assignee.email if assignee else "Unknown",
        created_by_email=creator.email if creator else "Unknown"
    )

@app.put("/tasks/{task_id}", response_model=schemas.Task)
def update_task(
    task_id: int,
    task_update: schemas.TaskUpdate,
    current_user: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    update_data = task_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(task, key, value)
    
    db.commit()
    db.refresh(task)
    return task

@app.delete("/tasks/{task_id}")
def delete_task(
    task_id: int,
    current_user: models.User = Depends(auth.get_current_admin),
    db: Session = Depends(get_db)
):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    db.delete(task)
    db.commit()
    return {"message": "Task deleted"}


# ==================== SESSION ENDPOINTS ====================

@app.get("/sessions", response_model=List[schemas.Session])
def get_my_sessions(
    status: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.GenerationSession).filter(
        models.GenerationSession.user_id == current_user.id
    )
    if status:
        query = query.filter(models.GenerationSession.status == status)
    return query.order_by(models.GenerationSession.started_at.desc()).all()

@app.get("/sessions/{session_id}", response_model=schemas.Session)
def get_session(
    session_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(models.GenerationSession).filter(
        models.GenerationSession.session_id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Users can only see their own sessions, admins can see all
    admin_email = os.getenv("ADMIN_EMAIL", "admin@example.com")
    if session.user_id != current_user.id and current_user.email != admin_email:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return session


# ==================== USER DASHBOARD ENDPOINT ====================

@app.get("/user/dashboard", response_model=schemas.UserDashboardStats)
def get_user_dashboard(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    total_generations = db.query(models.QuestionSet).filter(
        models.QuestionSet.owner_id == current_user.id
    ).count()
    total_questions = db.query(models.Question).join(models.QuestionSet).filter(
        models.QuestionSet.owner_id == current_user.id
    ).count()
    pending_tasks = db.query(models.Task).filter(
        models.Task.assignee_id == current_user.id,
        models.Task.status == "pending"
    ).count()
    completed_tasks = db.query(models.Task).filter(
        models.Task.assignee_id == current_user.id,
        models.Task.status == "completed"
    ).count()
    
    return schemas.UserDashboardStats(
        total_generations=total_generations,
        total_questions=total_questions,
        pending_tasks=pending_tasks,
        completed_tasks=completed_tasks
    )

# ==================== STATIC FILE SERVING ====================
# Mount static files for production (when frontend is built)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    assets_dir = frontend_dist / "assets"
    index_file = frontend_dist / "index.html"

    # Mount static assets only if directory exists
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    else:
        print(f"[WARN] Frontend assets directory not found at {assets_dir}. Skipping assets mount.")

    # Serve index.html for all routes (SPA support) only if index exists
    if index_file.exists():
        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            # If path starts with /api, /docs, /redoc, /openapi.json, let FastAPI handle it
            if full_path.startswith(("api/", "docs", "redoc", "openapi.json")):
                raise HTTPException(status_code=404)

            # Check if requesting a specific file
            file_path = frontend_dist / full_path
            if file_path.is_file():
                return FileResponse(file_path)

            # Otherwise serve index.html (SPA routing)
            return FileResponse(index_file)
    else:
        print(f"[WARN] Frontend index.html not found at {index_file}. Skipping SPA handler.")

if __name__ == "__main__":
    host = os.getenv("BACKEND_HOST", "0.0.0.0")
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)