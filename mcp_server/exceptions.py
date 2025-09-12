class MissingEnvironmentVariablesError(Exception):
    def __init__(self, missing_keys: list[str]):
        self.missing_keys = missing_keys
        super().__init__(f'Missing required environment variables: {", ".join(missing_keys)}')
