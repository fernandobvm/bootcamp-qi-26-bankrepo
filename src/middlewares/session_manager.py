from fastapi import FastAPI, Request

from database import clear_context, open_context


def register_session_manager_middleware(application: FastAPI) -> None:
    @application.middleware("http")
    async def manage_session(request: Request, call_next):
        # A requisição começa sem sessão nenhuma, e pode terminar assim.
        # Quem cria é o controller, ao pedir a sessão ao contexto.
        context = open_context()

        try:
            response = await call_next(request)
        except Exception:
            # Explodiu depois de a rota já ter mexido em alguma coisa: o
            # rascunho é rasgado aqui. Sem isto, a conexão voltaria pro
            # pool com uma transação abortada em cima dela, e a PRÓXIMA
            # requisição a pegar essa conexão levaria o erro de uma
            # requisição que não é a dela.
            #
            # Na prática o `close` logo abaixo também desfaria — ele
            # nunca devolve uma transação pendente pro pool. Esta linha
            # fica assim mesmo, dizendo a intenção em voz alta: o dia em
            # que alguém trocar o que vem depois, o combinado continua
            # escrito.
            if context.db_session is not None:
                context.db_session.rollback()
            raise
        finally:
            # Sempre. Deu certo, deu 404, explodiu: a conexão volta pro
            # pool nesta linha. E repare na pergunta antes do ponto: ela
            # é a guarda da armadilha contada na docstring.
            if context.db_session is not None:
                context.db_session.close()

            # E o contexto sai de circulação. Fora de uma requisição,
            # pedir o contexto tem que falhar alto — não devolver o desta
            # aqui, com a sessão já fechada.
            clear_context()

        return response
