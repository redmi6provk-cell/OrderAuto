from passlib.context import CryptContext
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")

hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/lewFBFlyg5qCvqvC."
print(pwd.verify("admin123", hash))
