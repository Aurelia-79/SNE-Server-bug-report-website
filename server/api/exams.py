from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from server.api.deps import get_current_user, get_db
from server.core.config import settings
from server.models.entities import (
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
from server.schemas.api import ExamGradeRequest, ExamPaperCreateRequest, ExamSubmissionCreateRequest
from server.services.domain import (
    build_exam_submission_mail,
    collect_exam_reviewer_emails,
    create_audit_log,
    ensure_exam_candidate,
    ensure_exam_paper_management_permission,
    ensure_exam_review_permission,
    evaluate_objective_answer,
    get_staff_or_404,
    is_hr_department,
    is_super_admin,
    send_notification_email,
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


def get_paper_or_404(db: Session, paper_id: int, *, require_active: bool = False) -> ExamPaper:
    query = select(ExamPaper).where(ExamPaper.id == paper_id)
    if require_active:
        query = query.where(ExamPaper.is_active.is_(True))
    paper = db.scalar(query)
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="试卷不存在或未启用。")
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


@router.get("/papers/available")
def list_available_papers(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_exam_candidate(current_user)
    papers = list(db.scalars(select(ExamPaper).where(ExamPaper.is_active.is_(True)).order_by(ExamPaper.id.desc())).all())
    submitted_ids = set(db.scalars(select(ExamSubmission.paper_id).where(ExamSubmission.user_id == current_user.id)).all())
    result = []
    for paper in papers:
        question_ids = list(db.scalars(select(ExamQuestion.id).where(ExamQuestion.paper_id == paper.id)).all())
        if not question_ids:
            continue
        item = serialize_paper(paper, [], include_answers=False)
        item["question_count"] = len(question_ids)
        item["submitted"] = paper.id in submitted_ids
        item["can_submit"] = paper.id not in submitted_ids
        result.append(item)
    return result


@router.get("/papers/{paper_id}")
def get_paper(paper_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_exam_candidate(current_user)
    paper = get_paper_or_404(db, paper_id, require_active=True)
    submitted = db.scalar(
        select(ExamSubmission.id).where(ExamSubmission.paper_id == paper_id, ExamSubmission.user_id == current_user.id).limit(1)
    )
    if submitted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="你已经提交过这份试卷，不能重复作答。")
    questions = list(db.scalars(select(ExamQuestion).where(ExamQuestion.paper_id == paper.id)).all())
    return serialize_paper(paper, questions, include_answers=False)


@router.get("/manage/paper")
def get_manage_paper(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_exam_paper_management_permission(current_user)
    paper = get_latest_paper(db)
    if not paper:
        return None
    return build_paper_payload(db, paper)


@router.get("/manage/papers")
def list_manage_papers(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ensure_exam_paper_management_permission(current_user)
    papers = list(db.scalars(select(ExamPaper).order_by(ExamPaper.id.desc())).all())
    result = []
    for paper in papers:
        question_count = len(list(db.scalars(select(ExamQuestion.id).where(ExamQuestion.paper_id == paper.id)).all()))
        submission_count = len(list(db.scalars(select(ExamSubmission.id).where(ExamSubmission.paper_id == paper.id)).all()))
        item = serialize_paper(paper, [], include_answers=False)
        item["question_count"] = question_count
        item["submission_count"] = submission_count
        item["can_delete"] = submission_count == 0
        result.append(item)
    return result


@router.get("/manage/papers/{paper_id}")
def get_manage_paper_by_id(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_exam_paper_management_permission(current_user)
    paper = get_paper_or_404(db, paper_id)
    return build_paper_payload(db, paper)


@router.post("/manage/paper")
def create_manage_paper(
    payload: ExamPaperCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_exam_paper_management_permission(current_user)
    validate_paper_request(payload)

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


@router.delete("/manage/paper/{paper_id}")
def delete_manage_paper(
    paper_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_exam_paper_management_permission(current_user)
    paper = db.scalar(select(ExamPaper).where(ExamPaper.id == paper_id))
    if not paper:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="试卷不存在。")
    has_submissions = db.scalar(select(ExamSubmission.id).where(ExamSubmission.paper_id == paper_id).limit(1))
    if has_submissions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该试卷已有答卷记录，不能删除。")
    questions = list(db.scalars(select(ExamQuestion).where(ExamQuestion.paper_id == paper_id)).all())
    for question in questions:
        db.delete(question)
    db.delete(paper)
    create_audit_log(
        db,
        actor_id=current_user.id,
        action="exam.paper.delete",
        target_type="paper",
        target_id=str(paper_id),
        detail={"title": paper.title, "question_count": len(questions)},
    )
    db.commit()
    return {"message": "试卷已删除。"}


@router.get("/submissions")
def list_submissions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = select(ExamSubmission).order_by(ExamSubmission.submitted_at.desc())
    if is_hr_department(current_user) or is_super_admin(current_user):
        submissions = list(db.scalars(query).all())
        return [build_submission_payload(db, item) for item in submissions]
    submissions = list(db.scalars(query).all())
    own_submissions = [item for item in submissions if item.user_id == current_user.id]
    return [build_submission_payload(db, item) for item in own_submissions]


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
    paper = get_paper_or_404(db, payload.paper_id, require_active=True)
    existing_submission = db.scalar(
        select(ExamSubmission.id).where(ExamSubmission.paper_id == paper.id, ExamSubmission.user_id == current_user.id).limit(1)
    )
    if existing_submission:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="你已经提交过这份试卷，不能重复提交。")
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
    # Notify exam reviewers
    reviewer_emails = collect_exam_reviewer_emails(db)
    if reviewer_emails:
        subject, text_body, html_body = build_exam_submission_mail(
            submission_id=submission.id,
            paper_title=paper.title,
            user_display_name=current_user.display_name,
            user_username=current_user.username,
            total_score=submission.total_score,
        )
        send_notification_email(db, to_addresses=reviewer_emails, subject=subject, body=text_body, html=html_body)
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

