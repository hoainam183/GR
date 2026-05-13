import asyncio
from config.settings import Settings
from query.reflection import QueryReflector

async def main():
    settings = Settings()
    # Override settings explicitly
    settings.reflection_max_tokens = 1024
    reflector = QueryReflector(settings=settings)
    
    query = "môn mạng máy tính được học ở kì mấy"
    res = reflector.reflect(
        query=query,
        user_context={"major": "Công nghệ thông tin", "major_code": "IT-E6"}
    )
    print("Reflected:", res["rewritten"])

if __name__ == "__main__":
    asyncio.run(main())

