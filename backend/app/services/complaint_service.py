from app.models.complaint import ComplaintStatus


ALLOWED_STATUS_TRANSITIONS: dict[ComplaintStatus, set[ComplaintStatus]] = {
    ComplaintStatus.OPEN: {
        ComplaintStatus.IN_PROGRESS,
        ComplaintStatus.RESOLVED,
    },
    ComplaintStatus.IN_PROGRESS: {
        ComplaintStatus.RESOLVED,
    },
    ComplaintStatus.RESOLVED: set(),  # terminal - closed forever
}


class InvalidStatusTransition(Exception):
    pass


def validate_status_transition(
    current: ComplaintStatus,
    target: ComplaintStatus,
) -> None:
    if current == target:
        raise InvalidStatusTransition(
            f"Complaint is already {current.value}."
        )

    allowed = ALLOWED_STATUS_TRANSITIONS.get(current, set())

    if target not in allowed:
        raise InvalidStatusTransition(
            f"Cannot transition complaint from {current.value} "
            f"to {target.value}."
        )
