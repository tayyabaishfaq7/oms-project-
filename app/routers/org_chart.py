"""
Organization chart (read-only, any logged-in user of the organization).

  GET /org-chart                     whole company as a tree (Chairman -> CEO -> General Manager -> ...)
  GET /org-chart?department_id=N     only one department's part of the tree
  GET /org-chart/text                the same tree drawn as plain text, easy to read in a browser/terminal

The tree is built from Position.reports_to_id. Each box lists the active employees who hold that position.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy import select

from app.core.database import DB
from app.dependencies import CurrentUser
from app.models import Department, Employee, Organization, Position
from app.schemas import OrgChartEmployee, OrgChartNode, OrgChartOut

router = APIRouter(prefix="/org-chart", tags=["Organization Chart"])


def _build(db, org_id: int, department_id: Optional[int]) -> tuple[list[OrgChartNode], int, int]:
    positions = db.scalars(
        select(Position).where(Position.organization_id == org_id).order_by(Position.rank, Position.id)
    ).all()
    if department_id is not None:
        positions = [p for p in positions if p.department_id == department_id]

    dept_names = {d.id: d.name for d in db.scalars(select(Department).where(Department.organization_id == org_id))}
    people: dict[int, list[OrgChartEmployee]] = {}
    for e in db.scalars(select(Employee).where(Employee.organization_id == org_id, Employee.status == "active")
                        .order_by(Employee.full_name)):
        people.setdefault(e.position_id, []).append(OrgChartEmployee(id=e.id, full_name=e.full_name))

    nodes = {p.id: OrgChartNode(
        position_id=p.id, title=p.title, rank=p.rank, department=dept_names.get(p.department_id),
        employees=people.get(p.id, []), children=[],
    ) for p in positions}

    roots: list[OrgChartNode] = []
    for p in positions:                    # already sorted by rank, so children come out in a stable order
        parent = nodes.get(p.reports_to_id) if p.reports_to_id else None
        (parent.children if parent else roots).append(nodes[p.id])
    return roots, len(nodes), sum(len(n.employees) for n in nodes.values())


@router.get("", response_model=OrgChartOut)
def org_chart(db: DB, user: CurrentUser, department_id: Optional[int] = None):
    if department_id is not None:
        dep = db.get(Department, department_id)
        if not dep or dep.organization_id != user.organization_id:
            raise HTTPException(status_code=404, detail="Department not found")
    roots, n_pos, n_emp = _build(db, user.organization_id, department_id)
    org = db.get(Organization, user.organization_id)
    return OrgChartOut(organization=org.name, total_positions=n_pos, total_employees=n_emp, chart=roots)


@router.get("/text", response_class=PlainTextResponse)
def org_chart_text(db: DB, user: CurrentUser, department_id: Optional[int] = None):
    roots, _, _ = _build(db, user.organization_id, department_id)
    org = db.get(Organization, user.organization_id)
    lines = [org.name]

    def draw(node: OrgChartNode, prefix: str, last: bool):
        who = ", ".join(e.full_name for e in node.employees) or "(vacant)"
        lines.append(f"{prefix}{'└── ' if last else '├── '}{node.title}  -  {who}")
        child_prefix = prefix + ("    " if last else "│   ")
        for i, child in enumerate(node.children):
            draw(child, child_prefix, i == len(node.children) - 1)

    for i, root in enumerate(roots):
        draw(root, "", i == len(roots) - 1)
    return "\n".join(lines)
