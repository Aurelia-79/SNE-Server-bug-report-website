from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import Base, engine
from app.models.entities import (
    BugComment,
    BugPriority,
    BugStatus,
    BugTicket,
    Department,
    EmploymentRecord,
    EmploymentRecordType,
    EmploymentStatus,
    ExamAnswer,
    ExamPaper,
    ExamQuestion,
    ExamSubmission,
    GameAdminRank,
    PromotionDemotionRecord,
    PunishmentRecord,
    QuestionType,
    RankChangeType,
    SubmissionStatus,
    SystemRole,
    User,
)
from app.services.domain import create_user_with_profile, utcnow


def init_database() -> None:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _migrate_staff_profiles_department_nullable()



def _migrate_staff_profiles_department_nullable() -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    old_table_name: str | None = None
    if "staff_profiles" not in table_names:
        if "staff_profiles_old" not in table_names:
            return
        old_table_name = "staff_profiles_old"
    if old_table_name is None:
        columns = {column["name"]: column for column in inspector.get_columns("staff_profiles")}
        department_column = columns.get("department")
        if not department_column or department_column.get("nullable", True):
            return
        old_table_name = "staff_profiles_old"
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            connection.execute(text("PRAGMA foreign_keys=OFF"))
            if "staff_profiles" in table_names:
                connection.execute(text("ALTER TABLE staff_profiles RENAME TO staff_profiles_old"))
            connection.execute(text("DROP INDEX IF EXISTS ix_staff_profiles_user_id"))
            Base.metadata.create_all(bind=engine)
            connection.execute(
                text(
                    f"""
                    INSERT INTO staff_profiles (id, user_id, department, position_title, employment_status, game_admin_rank, join_date, leave_date, notes)
                    SELECT id, user_id, department, position_title, employment_status, game_admin_rank, join_date, leave_date, notes
                    FROM {old_table_name}
                    """
                )
            )
            connection.execute(text(f"DROP TABLE {old_table_name}"))
            connection.execute(text("PRAGMA foreign_keys=ON"))
        return
    if engine.dialect.name == "mysql":
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE staff_profiles MODIFY COLUMN department VARCHAR(50) NULL"))
def seed_defaults(db: Session) -> None:
    if db.scalar(select(User.id).limit(1)):
        return

    super_admin = create_user_with_profile(
        db,
        username="superadmin",
        password="Admin@123",
        display_name="系统超管",
        system_role=SystemRole.SUPER_ADMIN,
        department=None,
        position_title="系统管理员",
        employment_status=EmploymentStatus.ACTIVE,
        game_admin_rank=None,
        join_date=date.today() - timedelta(days=180),
        notes="拥有全部权限。",
    )
    supervisor = create_user_with_profile(
        db,
        username="hrlead",
        password="Supervisor@123",
        display_name="跨部门主管",
        system_role=SystemRole.SUPERVISOR,
        department=None,
        position_title="主管",
        employment_status=EmploymentStatus.ACTIVE,
        game_admin_rank=None,
        join_date=date.today() - timedelta(days=120),
        notes="可跨部门查看后台数据。",
    )
    chief = create_user_with_profile(
        db,
        username="chief",
        password="Chief@123",
        display_name="总管示例",
        system_role=SystemRole.MEMBER,
        department=Department.GAME_ADMIN,
        position_title="总管",
        employment_status=EmploymentStatus.ACTIVE,
        game_admin_rank=GameAdminRank.CHIEF,
        join_date=date.today() - timedelta(days=300),
        notes="游戏管理员部门总管。",
    )
    senior = create_user_with_profile(
        db,
        username="senior",
        password="Senior@123",
        display_name="高级管理员示例",
        system_role=SystemRole.MEMBER,
        department=Department.GAME_ADMIN,
        position_title="高级管理员",
        employment_status=EmploymentStatus.ACTIVE,
        game_admin_rank=GameAdminRank.SENIOR,
        join_date=date.today() - timedelta(days=150),
    )
    admin = create_user_with_profile(
        db,
        username="gameadmin",
        password="AdminUser@123",
        display_name="管理员示例",
        system_role=SystemRole.MEMBER,
        department=Department.GAME_ADMIN,
        position_title="管理员",
        employment_status=EmploymentStatus.ACTIVE,
        game_admin_rank=GameAdminRank.ADMIN,
        join_date=date.today() - timedelta(days=45),
    )
    reviewer = create_user_with_profile(
        db,
        username="reviewer",
        password="Reviewer@123",
        display_name="审查期管理员示例",
        system_role=SystemRole.MEMBER,
        department=Department.GAME_ADMIN,
        position_title="审查期管理员",
        employment_status=EmploymentStatus.ACTIVE,
        game_admin_rank=GameAdminRank.REVIEW,
        join_date=date.today() - timedelta(days=20),
    )
    create_user_with_profile(
        db,
        username="publicity",
        password="Publicity@123",
        display_name="宣传成员示例",
        system_role=SystemRole.MEMBER,
        department=Department.PUBLICITY,
        position_title="宣传专员",
        employment_status=EmploymentStatus.ACTIVE,
        game_admin_rank=None,
        join_date=date.today() - timedelta(days=30),
    )
    create_user_with_profile(
        db,
        username="planner",
        password="Planner@123",
        display_name="策划成员示例",
        system_role=SystemRole.MEMBER,
        department=Department.PLANNING,
        position_title="活动策划",
        employment_status=EmploymentStatus.ACTIVE,
        game_admin_rank=None,
        join_date=date.today() - timedelta(days=35),
    )
    create_user_with_profile(
        db,
        username="developer",
        password="Developer@123",
        display_name="技术成员示例",
        system_role=SystemRole.MEMBER,
        department=Department.TECH,
        position_title="技术支持",
        employment_status=EmploymentStatus.ACTIVE,
        game_admin_rank=None,
        join_date=date.today() - timedelta(days=60),
    )

    db.flush()
    now = utcnow()
    for user in [super_admin, supervisor, chief, senior, admin, reviewer]:
        db.add(
            EmploymentRecord(
                user_id=user.id,
                record_type=EmploymentRecordType.JOIN,
                previous_status=EmploymentStatus.PENDING,
                new_status=EmploymentStatus.ACTIVE,
                reason="系统初始化示例数据",
                remark="默认入职记录",
                operator_id=super_admin.id,
                effective_at=now,
            )
        )

    db.add(
        PromotionDemotionRecord(
            user_id=admin.id,
            change_type=RankChangeType.PROMOTE,
            previous_rank=GameAdminRank.REVIEW,
            new_rank=GameAdminRank.ADMIN,
            reason="示例晋升记录",
            remark="通过考核",
            operator_id=chief.id,
            effective_at=now - timedelta(days=7),
        )
    )
    db.add(
        PunishmentRecord(
            user_id=reviewer.id,
            level="警告",
            reason="示例处罚记录",
            remark="值班迟到一次",
            operator_id=chief.id,
            effective_at=now - timedelta(days=2),
        )
    )

    paper = ExamPaper(
        title="游戏管理员入职考核卷",
        description="用于审查期管理员与管理员体系的入职考核。",
        pass_score=settings.default_pass_score,
        is_active=True,
    )
    db.add(paper)
    db.flush()

    questions = [
        ExamQuestion(
            paper_id=paper.id,
            order_no=1,
            prompt="发现玩家疑似违规时，第一步最合适的处理方式是？",
            question_type=QuestionType.SINGLE,
            options_json=[
                {"label": "A", "text": "立即封禁"},
                {"label": "B", "text": "先记录证据并按流程处理"},
                {"label": "C", "text": "让其他玩家处理"},
                {"label": "D", "text": "无视反馈"},
            ],
            correct_answer_json="B",
            score=20,
        ),
        ExamQuestion(
            paper_id=paper.id,
            order_no=2,
            prompt="以下哪些内容属于合格管理在值班时应完成的工作？",
            question_type=QuestionType.MULTIPLE,
            options_json=[
                {"label": "A", "text": "巡查玩家反馈"},
                {"label": "B", "text": "维护聊天秩序"},
                {"label": "C", "text": "恶意偏袒熟人"},
                {"label": "D", "text": "及时上报重大问题"},
            ],
            correct_answer_json=["A", "B", "D"],
            score=30,
        ),
        ExamQuestion(
            paper_id=paper.id,
            order_no=3,
            prompt="“管理员处理举报时应优先保留证据链”这句话是否正确？",
            question_type=QuestionType.BOOLEAN,
            options_json=[{"label": "true", "text": "正确"}, {"label": "false", "text": "错误"}],
            correct_answer_json=True,
            score=10,
        ),
        ExamQuestion(
            paper_id=paper.id,
            order_no=4,
            prompt="请简述你遇到多人同时举报时的处理思路。",
            question_type=QuestionType.TEXT,
            options_json=None,
            correct_answer_json=None,
            score=40,
        ),
    ]
    db.add_all(questions)
    db.flush()

    answer_map = {question.order_no: question for question in questions}
    submission_one = ExamSubmission(
        paper_id=paper.id,
        user_id=admin.id,
        status=SubmissionStatus.GRADED,
        objective_score=60,
        subjective_score=28,
        total_score=88,
        overall_comment="处理思路完整，具备上岗条件。",
        submitted_at=now - timedelta(days=3),
        graded_at=now - timedelta(days=2),
        grader_id=chief.id,
    )
    submission_two = ExamSubmission(
        paper_id=paper.id,
        user_id=reviewer.id,
        status=SubmissionStatus.GRADED,
        objective_score=40,
        subjective_score=20,
        total_score=60,
        overall_comment="基础合格，需继续加强高压场景处理能力。",
        submitted_at=now - timedelta(days=1),
        graded_at=now,
        grader_id=senior.id,
    )
    db.add_all([submission_one, submission_two])
    db.flush()

    db.add_all(
        [
            ExamAnswer(
                submission_id=submission_one.id,
                question_id=answer_map[1].id,
                answer_json="B",
                objective_score=20,
                manual_score=None,
                final_score=20,
            ),
            ExamAnswer(
                submission_id=submission_one.id,
                question_id=answer_map[2].id,
                answer_json=["A", "B", "D"],
                objective_score=30,
                manual_score=None,
                final_score=30,
            ),
            ExamAnswer(
                submission_id=submission_one.id,
                question_id=answer_map[3].id,
                answer_json=True,
                objective_score=10,
                manual_score=None,
                final_score=10,
            ),
            ExamAnswer(
                submission_id=submission_one.id,
                question_id=answer_map[4].id,
                answer_json="先分类收集举报内容，再同步记录时间线，优先核验高风险案件。",
                objective_score=0,
                manual_score=28,
                final_score=28,
                grader_comment="答案完整，现场应变意识较好。",
            ),
            ExamAnswer(
                submission_id=submission_two.id,
                question_id=answer_map[1].id,
                answer_json="B",
                objective_score=20,
                manual_score=None,
                final_score=20,
            ),
            ExamAnswer(
                submission_id=submission_two.id,
                question_id=answer_map[2].id,
                answer_json=["A", "B"],
                objective_score=0,
                manual_score=None,
                final_score=0,
            ),
            ExamAnswer(
                submission_id=submission_two.id,
                question_id=answer_map[3].id,
                answer_json=True,
                objective_score=10,
                manual_score=None,
                final_score=10,
            ),
            ExamAnswer(
                submission_id=submission_two.id,
                question_id=answer_map[4].id,
                answer_json="优先安抚玩家，再看哪个举报证据更清晰。",
                objective_score=0,
                manual_score=20,
                final_score=20,
                grader_comment="基本正确，但缺少同步上报与复盘意识。",
            ),
        ]
    )

    ticket = BugTicket(
        title="值班统计页图表刷新延迟",
        module="成绩分析",
        priority=BugPriority.MEDIUM,
        status=BugStatus.PROCESSING,
        reporter_id=senior.id,
        assignee_id=supervisor.id,
        reproduce_steps="进入图表页后切换等级筛选，图表数据不会立即刷新。",
        expected_result="切换等级后，图表应立即根据筛选条件重绘。",
        actual_result="图表需刷新页面才会更新。",
        resolution=None,
    )
    db.add(ticket)
    db.flush()
    db.add(
        BugComment(
            ticket_id=ticket.id,
            author_id=supervisor.id,
            content="已复现，排查前端筛选条件 watch 逻辑。",
        )
    )
    db.commit()


def normalize_super_admin_profiles(db: Session) -> None:
    users = list(db.scalars(select(User).where(User.system_role == SystemRole.SUPER_ADMIN)).all())
    changed = False
    for user in users:
        profile = user.profile
        if not profile:
            continue
        if profile.department is not None:
            profile.department = None
            changed = True
        if profile.game_admin_rank is not None:
            profile.game_admin_rank = None
            changed = True
    if changed:
        db.commit()

def bootstrap_super_admin(db: Session) -> None:
    if not settings.bootstrap_super_admin_username or not settings.bootstrap_super_admin_password:
        return
    existing = db.scalar(select(User).where(User.username == settings.bootstrap_super_admin_username))
    if existing:
        return
    create_user_with_profile(
        db,
        username=settings.bootstrap_super_admin_username,
        password=settings.bootstrap_super_admin_password,
        display_name=settings.bootstrap_super_admin_display_name,
        system_role=SystemRole.SUPER_ADMIN,
        department=None,
        position_title='系统超管',
        employment_status=EmploymentStatus.ACTIVE,
        game_admin_rank=None,
        join_date=date.today(),
        notes='生产环境初始超管',
    )
    db.commit()


