from openai import OpenAI
import config

client = OpenAI(api_key=config.OPENAI_KEY)
models = client.models.list()
print([m.id for m in models.data])

