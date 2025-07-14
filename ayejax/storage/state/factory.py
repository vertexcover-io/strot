from .interface import StateStorageInterface
from .memory import InMemoryStateStorage


class StateStorageFactory:
    """Factory for creating state storage instances."""
    
    @staticmethod
    def create_storage(backend_type: str, **kwargs) -> StateStorageInterface:
        """Create state storage instance based on backend type."""
        if backend_type == "memory":
            return InMemoryStateStorage()
        elif backend_type == "postgresql":
            # Future implementation
            raise NotImplementedError("PostgreSQL backend not implemented yet")
        else:
            raise ValueError(f"Unknown backend type: {backend_type}")