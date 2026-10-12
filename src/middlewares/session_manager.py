from fastapi import FastAPI, Request

from database import clear_context, open_context


def register_session_manager_middleware(application: FastAPI) -> None:
    @application.middleware("http")
    async def manage_session(request: Request, call_next):
        context = open_context()

        try:
            response = await call_next(request)
        except Exception:
            # Desfaz o que a rota deixou pela metade antes de a conexão voltar ao pool.
            if context.db_session is not None:
                context.db_session.rollback()
            raise
        finally:
            if context.db_session is not None:
                context.db_session.close()

            clear_context()

        return response
