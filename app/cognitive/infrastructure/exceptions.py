class GraphException(Exception):
    """Base exception for all knowledge graph related errors."""
    pass

class AliasException(GraphException):
    """Raised when an alias registration or resolution operation fails."""
    pass

class ProfileException(Exception):
    """Raised when user profile loading, updating, or synchronization fails."""
    pass

class EntityResolutionException(GraphException):
    """Raised when duplicate entity matching or resolving canonical identities errors."""
    pass

class RelationshipException(GraphException):
    """Raised when relation checks, weight validations, or path traversals fail."""
    pass
