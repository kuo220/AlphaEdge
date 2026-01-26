from trader.pipeline.updaters.base import BaseDataUpdater


class FinMindUpdater(BaseDataUpdater):
    """FinMind Updater"""

    def __init__(self):
        super().__init__()
        self.setup()

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Updater"""
        pass

    def update(self, *args, **kwargs) -> None:
        """Update the Database"""
        pass
