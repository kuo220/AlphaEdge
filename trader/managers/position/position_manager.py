from trader.managers.position.base import BasePositionManager


class PositionManager(BasePositionManager):
    """Position Manager"""

    def __init__(self):
        super().__init__()

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Position Manager"""
        pass
