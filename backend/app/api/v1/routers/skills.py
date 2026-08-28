"""Authoring skills, and reading a community's complaint categories.

**Reading the catalogue is not here.** ``GET /skills`` lives in
``service_providers.py`` and has since ``0034``, because it exists for the
service person's registration screen and any signed-in person may call it. This
module is the half only administrators and department managers may reach:
adding a trade to the global catalogue, and saying which trades a department
needs.

The guard is two-layered, the same shape ``department_hiring.py`` documents at
its head. ``require_admin_or_manager`` on the router is coarse -- it only asks
whether the caller is an admin or a manager *somewhere*. The real question,
whether they manage **this** department, is asked by ``can_manage_department``
inside each RPC, because a manager of one community must not be able to edit
another's skills by putting its id in a path.

``GET /complaint-categories`` sits here rather than beside the department CRUD
because of what it is *for*: the category box on the department form, whose
whole job is to stop somebody inventing "Plumbling" beside "Plumbing". It is
the same duplicate-prevention problem as the skill box, and the two are read by
the same screen.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, Response, status

from app.api.admin_deps import require_admin_or_manager, require_csrf_unsafe
from app.api.deps import get_request_client
from app.domain.common_schemas import MessageResult
from app.domain.department_schemas import (
    AddDepartmentSkillRequest,
    SetDepartmentSkillsRequest,
)
from app.domain.schemas import MembershipContext
from app.domain.service_provider_schemas import Skill
from app.domain.skill_schemas import ComplaintCategory, CreateSkillRequest, SkillCreated
from app.services import skills_service as service
from supabase import Client

router = APIRouter(
    tags=["skills"],
    dependencies=[Depends(require_admin_or_manager), Depends(require_csrf_unsafe)],
)


@router.post(
    "/skills",
    response_model=SkillCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Add a trade to the global catalogue",
)
def create_skill(
    body: CreateSkillRequest,
    response: Response,
    client: Client = Depends(get_request_client),
) -> SkillCreated:
    """Create a skill, or return the one that already answers to that name.

    The match is case- and whitespace-insensitive, so ``"  plumbing "`` finds
    ``Plumbing`` rather than creating a second one. **This is not an error and
    is not reported as one** -- somebody typing a trade that already exists has
    asked a reasonable question and gets a usable answer.

    Responds **201** when the skill was created and **200** when it already
    existed, matching ``created`` in the body. A retired trade asked for again
    is reactivated rather than duplicated.

    The catalogue is global: a skill added by one community is immediately
    available to every other, which is the point -- one vocabulary means a
    plumber claims "Plumbing" once and the hiring search matches everywhere.
    """
    result = service.create(client, body=body)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return result


@router.get(
    "/complaint-categories",
    response_model=list[ComplaintCategory],
    summary="This community's complaint categories",
)
def list_categories(
    membership: MembershipContext = Depends(require_admin_or_manager),
    client: Client = Depends(get_request_client),
) -> list[ComplaintCategory]:
    """Every category this community has, with the trade each one resolves to.

    ``skillName`` is null when the category's name matches no trade. That is
    not an error -- a community may name a category the catalogue has no word
    for -- but it has consequences nobody could see until now: a category with
    no trade behind it matches no service person in any hiring search. The form
    shows it as a warning rather than leaving it silent.

    ``departmentCount`` is how many departments claim the category. Zero means
    complaints filed under it reach no department at all.
    """
    return service.list_categories(
        client, membership_id=membership.id, community_id=membership.community_id
    )


@router.get(
    "/departments/{department_id}/skills",
    response_model=list[Skill],
    summary="Skills a department needs",
)
def list_department_skills(
    department_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> list[Skill]:
    """The trades this department employs, alphabetically.

    Empty for every department that has not chosen any: skills are **never**
    inherited from the department's complaint categories. The two answer
    different questions, and inheriting one from the other would give every
    department a skill list nobody picked.
    """
    return service.list_department_skills(client, department_id=department_id)


@router.put(
    "/departments/{department_id}/skills",
    response_model=list[Skill],
    summary="Replace a department's skills",
)
def set_department_skills(
    body: SetDepartmentSkillsRequest,
    department_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> list[Skill]:
    """Make the department's skill set exactly ``skillIds``.

    Every id is checked to name an active skill **before** anything is deleted,
    so a request carrying one bad id fails with 422 rather than emptying the
    list on its way to failing.

    Returns the set as it now stands, read back from the database rather than
    echoed, so a caller learns what actually landed.
    """
    return service.set_department_skills(
        client, department_id=department_id, skill_ids=body.skill_ids
    )


@router.post(
    "/departments/{department_id}/skills",
    response_model=SkillCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Add a skill to a department by name",
)
def add_department_skill(
    body: AddDepartmentSkillRequest,
    response: Response,
    department_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> SkillCreated:
    """The department form's "Add skill" button, in one call.

    Creates the trade in the global catalogue if no case-insensitive match
    exists, then attaches it to this department. **One call rather than two**,
    because create-then-attach can half-fail, and a skill created but not
    attached is catalogue litter nobody asked for.

    Responds **201** when the skill was newly created and **200** when an
    existing one was attached. Attaching a skill the department already has is
    not an error -- it is idempotent and returns the same body.
    """
    result = service.add_department_skill(
        client, department_id=department_id, name=body.name
    )
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return result


@router.delete(
    "/departments/{department_id}/skills/{skill_id}",
    response_model=MessageResult,
    summary="Detach a skill from a department",
)
def remove_department_skill(
    department_id: str = Path(...),
    skill_id: str = Path(...),
    client: Client = Depends(get_request_client),
) -> MessageResult:
    """Remove one trade from this department's list.

    The skill itself is untouched: it is global, and another department almost
    certainly needs it. Detaching one the department does not have is a no-op
    rather than a 404 -- the caller's intent is already satisfied.
    """
    service.remove_department_skill(
        client, department_id=department_id, skill_id=skill_id
    )
    return MessageResult(message="Skill removed from the department.")
