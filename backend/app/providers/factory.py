"""Factory for creating data provider instances."""

import logging
from typing import Dict, Type, Optional
from .base import BaseDataProvider
from .betfair import BetfairProvider


class DataProviderFactory:
    """Factory class for creating data provider instances."""
    
    # Registry of available providers
    _providers: Dict[str, Type[BaseDataProvider]] = {
        "betfair": BetfairProvider,
        # Future providers can be added here:
        # "pinnacle": PinnacleProvider,
        # "smarkets": SmarketsProvider,
        # "betdaq": BetdaqProvider,
    }
    
    @classmethod
    def register_provider(cls, name: str, provider_class: Type[BaseDataProvider]) -> None:
        """
        Register a new provider type.
        
        Args:
            name: Name identifier for the provider
            provider_class: Provider class that extends BaseDataProvider
        """
        if not issubclass(provider_class, BaseDataProvider):
            raise TypeError(f"{provider_class} must be a subclass of BaseDataProvider")
            
        cls._providers[name.lower()] = provider_class
        logging.info(f"Registered provider: {name}")
    
    @classmethod
    def create_provider(
        cls, 
        provider_name: str, 
        logger: Optional[logging.Logger] = None
    ) -> BaseDataProvider:
        """
        Create a provider instance by name.
        
        Args:
            provider_name: Name of the provider to create
            logger: Optional logger instance
            
        Returns:
            Instance of the requested provider
            
        Raises:
            ValueError: If provider name is not recognized
        """
        provider_name = provider_name.lower()
        
        if provider_name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown provider '{provider_name}'. "
                f"Available providers: {available}"
            )
        
        provider_class = cls._providers[provider_name]
        
        # Create logger if not provided
        if logger is None:
            logger = logging.getLogger(f"providers.{provider_name}")
            
        # Create and return provider instance
        return provider_class(logger=logger)
    
    @classmethod
    def list_providers(cls) -> list:
        """
        Get list of available provider names.
        
        Returns:
            List of registered provider names
        """
        return list(cls._providers.keys())
    
    @classmethod
    def create_multiple_providers(
        cls,
        provider_names: list,
        logger: Optional[logging.Logger] = None
    ) -> Dict[str, BaseDataProvider]:
        """
        Create multiple provider instances.
        
        Args:
            provider_names: List of provider names to create
            logger: Optional logger instance
            
        Returns:
            Dictionary mapping provider names to instances
        """
        providers = {}
        
        for name in provider_names:
            try:
                providers[name] = cls.create_provider(name, logger)
                logging.info(f"Created provider: {name}")
            except Exception as e:
                logging.error(f"Failed to create provider {name}: {e}")
                
        return providers