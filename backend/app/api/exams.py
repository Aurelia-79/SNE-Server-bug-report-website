from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.entities import (
    Department,
    ExamAnswer,
    ExamAttachment,
    ExamPaper,
    ExamQuestion,
    ExamSubmission,
    GameAdminRank,
    QuestionType,
    SubmissionStatus,
    SystemRole,
    User,
)
from app.schemas.api import ExamGradeRequest, ExamPaperCreateRequest, ExamSubmissionCreateRequest
from app.services.domain import (
    create_audit_log,
    ensure_exam_candidate,
    ensure_exam_paper_management_permission,
    ensure_exam_review_permission,
    evaluate_objective_answer,
    get_staff_or_404,
    is_hr_department,
    is_supervisor,
    serialize_paper,
    serialize_submission,
    store_upload,
    utcnow,
)

router = APIRouter(prefix="/api/exams", tags=["exams"])


def get_active_paper_or_404(db: Session) -> ExamPaper:
    paper = db.scalar(select(ExamPaper).where(ExamPaper.is_active.is_(True)).order_by(ExamPaper.id.desc()))
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="当前没有启用中的试卷。")
    return paper


def get_latest_paper(db: Session) -> ExamPaper | None:
    return db.scalar(select(ExamPaper).order_by(ExamPaper.id.desc()))


def build_submission_payload(db: Session, submission: ExamSubmission) -> dict:
    owner = get_staff_or_404(db, submission.user_id)
    paper = db.scalar(select(ExamPaper).where(ExamPaper.id == submission.paper_id))
    questions = list(
        db.scalars(select(ExamQuestion).where(ExamQuestion.paper_id == submission.paper_id).order_by(ExamQuestion.order_no)).all()
    )
    answers = list(
        db.scalars(select(ExamAnswer).where(ExamAnswer.submission_id == submission.id).order_by(ExamAnswer.id)).all()
    )
    attachments = list(
        db.scalars(select(ExamAttachment).where(ExamAttachment.submission_id == submission.id).order_by(ExamAttachment.id)).all()
    )
    grader = get_staff_or_404(db, submission.grader_id) if submission.grader_id else None
    return serialize_submission(submission, owner, paper, questions, answers, attachments, grader)


def build_paper_payload(db: Session, paper: ExamPaper) -> dict:
    questions = list(
        db.scalars(select(ExamQuestion).where(ExamQuestion.paper_id == paper.id).order_by(ExamQuestion.order_no)).all()
    )
    return serialize_paper(paper, questions, include_answers=True)


def validate_paper_request(payload: ExamPaperCreateRequest) -> None:
    if not payload.questions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="试卷至少需要一道题。")
    for question in payload.questions:
        if question.question_type not in {"single_choice", "text"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持选择题和简答题。")
        if question.question_type == "single_choice":
            if not question.options or len(question.options) < 2:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="选择题至少需要两个选项。")
            labels = [item.label for item in question.options]
            if len(labels) != len(set(labels)):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="选择题选项标签不能重复。")
            if question.correct_answer not in labels:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="选择题必须指定正确答案。")
        if question.question_type == "text":
            if question.options:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="简答题不需要选项。")
            if question.correct_answer:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="简答题不需要标准答案。")


@router.get("/paper")
def get_active_paper(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_exam_candidate(current_user)
    paper = get_active_paper_or_404(db)
    questions = list(db.scalars(select(ExamQuestion).where(ExamQuestion.paper_id == paper.id)).all())
    return serialize_paper(paper, questions, include_answers=False)


@router.get("/manage/paper")
def get_manage_paper(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_exam_paper_management_permission(current_user)
    paper = get_latest_paper(db)
    if not paper:
        return None
    return build_paper_payload(db, paper)


@router.post("/manage/paper")
def create_manage_paper(
    payload: ExamPaperCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_exam_paper_management_permission(current_user)
    validate_paper_request(payload)

    db.execute(update(ExamPaper).values(is_active=False))
    paper = ExamPaper(
        title=payload.title,
        description=payload.description,
        pass_score=payload.pass_score,
        is_active=True,
    )
    db.add(paper)
    db.flush()

    rows = []
    for question in sorted(payload.questions, key=lambda item: item.order_no):
        rows.append(
            ExamQuestion(
                paper_id=paper.id,
                order_no=question.order_no,
                prompt=question.prompt,
                question_type=QuestionType.SINGLE if question.question_type == "single_choice" else QuestionType.TEXT,
                options_json=[item.model_dump() for item in question.options] if question.options else None,
                correct_answer_json=question.correct_answer if question.question_type == "single_choice" else None,
                score=question.score,
            )
        )
    db.add_all(rows)
    create_audit_log(
        db,
        actor_id=current_user.id,
        action="exam.paper.create",
        target_type="paper",
        target_id=str(paper.id),
        detail={"title": paper.title, "question_count": len(rows)},
    )
    db.commit()
    return build_paper_payload(db, paper)


@router.get("/submissions")
def list_submissions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = select(ExamSubmission).order_by(ExamSubmission.submitted_at.desc())
    if is_hr_department(current_user) or is_supervisor(current_user):
        submissions = list(db.scalars(query).all())
        return [build_submission_payload(db, item) for item in submissions]
    if current_user.system_role == SystemRole.MEMBER:
        if current_user.profile.department == Department.GAME_ADMIN and current_user.profile.game_admin_rank in {
            GameAdminRank.SENIOR,
            GameAdminRank.CHIEF,
        }:
            submissions = list(db.scalars(query).all())
            allowed = []
            for item in submissions:
                owner = get_staff_or_404(db, item.user_id)
                try:
                    ensure_exam_review_permission(current_user, owner)
                    allowed.append(build_submission_payload(db, item))
                except HTTPException:
                    continue
            return allowed
        submissions = list(db.scalars(query.where(ExamSubmission.user_id == current_user.id)).all())
        return [build_submission_payload(db, item) for item in submissions]
    submissions = list(db.scalars(query).all())
    return [build_submission_payload(db, item) for item in submissions]


@router.get("/submissions/{submission_id}")
def get_submission_detail(submission_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    submission = db.scalar(select(ExamSubmission).where(ExamSubmission.id == submission_id))
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="答卷不存在。")
    owner = get_staff_or_404(db, submission.user_id)
    if current_user.id != owner.id:
        ensure_exam_review_permission(current_user, owner)
    return build_submission_payload(db, submission)


@router.post("/submissions")
def create_submission(
    payload: ExamSubmissionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_exam_candidate(current_user)
    if current_user.profile.department != Department.GAME_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅游戏管理员部门成员可提交试卷。")
    paper = get_active_paper_or_404(db)
    questions = list(
        db.scalars(select(ExamQuestion).where(ExamQuestion.paper_id == paper.id).order_by(ExamQuestion.order_no)).all()
    )
    question_map = {question.id: question for question in questions}
    if len(payload.answers) != len(questions):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请完成全部题目后再提交。")
    answers_by_question = {item.question_id: item.answer for item in payload.answers}
    if set(answers_by_question.keys()) != set(question_map.keys()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="提交题目与试卷不匹配。")

    submission = ExamSubmission(
        paper_id=paper.id,
        user_id=current_user.id,
        status=SubmissionStatus.PENDING_REVIEW,
        objective_score=0,
        subjective_score=0,
        total_score=0,
        overall_comment=payload.overall_comment,
    )
    db.add(submission)
    db.flush()

    objective_total = 0.0
    answer_ids: list[dict[str, int]] = []
    has_subjective = False
    for question in questions:
        answer_value = answers_by_question[question.id]
        objective_score = evaluate_objective_answer(question, answer_value)
        if question.question_type == QuestionType.TEXT:
            has_subjective = True
        answer = ExamAnswer(
            submission_id=submission.id,
            question_id=question.id,
            answer_json=answer_value,
            objective_score=objective_score,
            manual_score=None,
            final_score=objective_score,
        )
        db.add(answer)
        db.flush()
        objective_total += objective_score
        answer_ids.append({"question_id": question.id, "answer_id": answer.id})

    submission.objective_score = objective_total
    submission.total_score = objective_total
    if not has_subjective:
        submission.status = SubmissionStatus.GRADED
        submission.graded_at = utcnow()
    create_audit_log(
        db,
        actor_id=current_user.id,
        action="exam.submit",
        target_type="submission",
        target_id=str(submission.id),
        detail={"paper_id": paper.id},
    )
    db.commit()
    return {"submission_id": submission.id, "answer_ids": answer_ids}


@router.post("/submissions/{submission_id}/attachments")
def upload_submission_attachments(
    submission_id: int,
    answer_id: int | None = Form(default=None),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = db.scalar(select(ExamSubmission).where(ExamSubmission.id == submission_id))
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="答卷不存在。")
    if submission.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅答卷所有者可上传附件。")
    if answer_id:
        answer = db.scalar(
            select(ExamAnswer).where(ExamAnswer.id == answer_id, ExamAnswer.submission_id == submission_id)
        )
        if not answer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="题目答案不存在。")

    records = []
    for file in files:
        stored_name, relative_path, size, mime_type = store_upload(file, "exams")
        attachment = ExamAttachment(
            submission_id=submission_id,
            answer_id=answer_id,
            stored_name=stored_name,
            original_name=file.filename or stored_name,
            relative_path=relative_path,
            mime_type=mime_type,
            size=size,
            uploaded_by=current_user.id,
        )
        db.add(attachment)
        db.flush()
        records.append({"id": attachment.id, "name": attachment.original_name})
    create_audit_log(
        db,
        actor_id=current_user.id,
        action="exam.attachments.upload",
        target_type="submission",
        target_id=str(submission_id),
        detail={"answer_id": answer_id, "count": len(records)},
    )
    db.commit()
    return {"message": "附件上传成功。", "files": records}


@router.post("/submissions/{submission_id}/grade")
def grade_submission(
    submission_id: int,
    payload: ExamGradeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    submission = db.scalar(select(ExamSubmission).where(ExamSubmission.id == submission_id))
    if not submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="答卷不存在。")
    owner = get_staff_or_404(db, submission.user_id)
    ensure_exam_review_permission(current_user, owner)
    answers = list(db.scalars(select(ExamAnswer).where(ExamAnswer.submission_id == submission.id)).all())
    answer_map = {answer.id: answer for answer in answers}
    questions = {
        question.id: question
        for question in db.scalars(select(ExamQuestion).where(ExamQuestion.paper_id == submission.paper_id)).all()
    }

    for grade_item in payload.answers:
        answer = answer_map.get(grade_item.answer_id)
        if not answer:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="存在无效的题目答案。")
        question = questions[answer.question_id]
        if question.question_type != QuestionType.TEXT:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅简答题支持手动评分。")
        if grade_item.manual_score < 0 or grade_item.manual_score > question.score:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="题目得分超出允许范围。")
        answer.manual_score = grade_item.manual_score
        answer.final_score = grade_item.manual_score
        answer.grader_comment = grade_item.grader_comment

    objective_score = sum(answer.objective_score for answer in answers)
    subjective_score = sum((answer.manual_score or 0) for answer in answers if questions[answer.question_id].question_type == QuestionType.TEXT)
    submission.objective_score = objective_score
    submission.subjective_score = subjective_score
    submission.total_score = objective_score + subjective_score
    submission.overall_comment = payload.overall_comment
    submission.status = SubmissionStatus.GRADED
    submission.grader_id = current_user.id
    submission.graded_at = utcnow()

    create_audit_log(
        db,
        actor_id=current_user.id,
        action="exam.grade",
        target_type="submission",
        target_id=str(submission.id),
        detail={"total_score": submission.total_score},
    )
    db.commit()
    return build_submission_payload(db, submission)


@router.get("/attachments/{attachment_id}")
def download_exam_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attachment = db.scalar(select(ExamAttachment).where(ExamAttachment.id == attachment_id))
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="附件不存在。")
    submission = db.scalar(select(ExamSubmission).where(ExamSubmission.id == attachment.submission_id))
    owner = get_staff_or_404(db, submission.user_id)
    if current_user.id != owner.id:
        ensure_exam_review_permission(current_user, owner)
    file_path = settings.upload_dir / attachment.relative_path
    return FileResponse(str(file_path), media_type=attachment.mime_type, filename=attachment.original_name)
