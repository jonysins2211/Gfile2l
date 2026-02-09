# ya Lili ya Lili
FROM python:3.11.8-slim
WORKDIR /app
COPY . /app
# RUN pip install -r requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 5000
CMD ["python", "bot.py"]
