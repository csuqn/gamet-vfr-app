# Para alojar no Hugging Face Spaces (tipo "Docker") ou no Render.
# O motor vem do app.py na raiz do repositório — por isso a imagem copia
# o repositório inteiro e não só esta pasta.
FROM python:3.12-slim
WORKDIR /srv
COPY . .
RUN pip install --no-cache-dir -r nicegui_app/requirements.txt
ENV PORT=7860
EXPOSE 7860
WORKDIR /srv/nicegui_app
CMD ["python", "main.py"]
