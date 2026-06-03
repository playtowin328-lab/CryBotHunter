class TelegramCommandService:
    def handle(self, command: str) -> str:
        commands = {
            "/start": "Trading bot notifications enabled.",
            "/stop": "Trading bot notifications disabled.",
            "/balance": "Balance endpoint is available in the dashboard API.",
            "/stats": "Stats endpoint is available in the dashboard API.",
            "/positions": "Positions endpoint is available in the positions API.",
        }
        return commands.get(command, "Unknown command.")
