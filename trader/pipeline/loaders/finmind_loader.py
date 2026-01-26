from trader.pipeline.loaders.base import BaseDataLoader


class FinMindLoader(BaseDataLoader):
    """FinMind Loader"""

    def __init__(self):
        super().__init__()
        self.setup()

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Loader"""
        pass

    def connect(self) -> None:
        """Connect to the Database"""
        pass

    def disconnect(self) -> None:
        """Disconnect the Database"""
        pass

    def create_db(self, *args, **kwargs) -> None:
        """Create New Database"""
        pass

    def add_to_db(self, *args, **kwargs) -> None:
        """Add Data into Database"""
        pass
