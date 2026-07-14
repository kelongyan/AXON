from typing import Final


class WorkflowNotFoundError(LookupError):
    pass


class WorkflowValidationError(ValueError):
    pass


class RunNotFoundError(LookupError):
    pass


class RunExecutionError(RuntimeError):
    pass


class ApprovalNotFoundError(LookupError):
    pass


class ApprovalStateError(ValueError):
    pass


class RunWaitingForApproval(RuntimeError):
    pass


EXECUTABLE_PHASE6_NODE_TYPES: Final = {"start", "retrieval", "agent", "tool", "approval", "end"}
PLANNED_VISUAL_NODE_TYPES: Final = {"condition"}
TERMINAL_RUN_STATUSES: Final = {"succeeded", "failed", "cancelled"}
