"""Domain exceptions with safe, actionable messages."""


class BreakFuserError(Exception):
    """Base package error."""


class ConfigurationError(BreakFuserError):
    """Configuration is missing or invalid."""


class BudgetExhausted(BreakFuserError):
    """A hard request or session budget was exhausted."""


class SecurityBlocked(BreakFuserError):
    """A privacy or tool-security guard blocked an operation."""


class VerificationError(BreakFuserError):
    """A draft could not be repaired to match verified facts."""


class AdapterError(BreakFuserError):
    """An upstream adapter returned an invalid or unsuccessful response."""


class TaskNotFound(BreakFuserError):
    """An asynchronous task identifier is unknown."""


class HarvestStopped(BreakFuserError):
    """Harvesting stopped at a configured policy boundary."""
