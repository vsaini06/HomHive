from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter

from .graphql.schema import schema


app = FastAPI(
    title="HomHive API",
    version="0.1.0",
)


graphql_app = GraphQLRouter(
    schema
)

app.include_router(
    graphql_app,
    prefix="/graphql",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
    }