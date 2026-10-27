class AppError(Exception):
    """业务异常基类：不依赖 FastAPI，由全局处理器翻译成 HTTP 响应。"""

    status_code = 400
    code = "APP_ERROR"
    message = "请求处理失败"

    def __init__(self, message: str | None = None) -> None:
        self.message = message or self.message
        super().__init__(self.message)


class UsernameAlreadyExistsError(AppError):
    status_code = 409
    code = "USERNAME_EXISTS"
    message = "用户名已存在"


class InvalidCredentialsError(AppError):
    status_code = 401
    code = "INVALID_CREDENTIALS"
    message = "用户名或密码错误"
