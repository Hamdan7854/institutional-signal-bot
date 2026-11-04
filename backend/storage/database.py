class DatabaseHandler:
    def __init__(self):
        pass

    def log_signal(self, symbol, direction, outcome):
        # Database storage logic for tracking signals and performance
        pass

    def save_signal(self, symbol, details, confidence):
        """
        Wrapper to save signals matching main.py call.
        """
        self.log_signal(symbol, details, confidence)
