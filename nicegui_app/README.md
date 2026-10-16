# Protótipo NiceGUI

Mesma app, outra interface. **Não substitui a app Streamlit publicada**:
corre em paralelo até se decidir.

- O motor é o mesmo: `motor.py` executa as secções de `app.py` que os testes
  usam (parser, geometria, decisão, PDF, componentes HTML) e a secção de rede.
  Uma correcção no `app.py` vale para as duas interfaces.
- `main.py` tem só a interface e a mesma lógica de SIGMETs / recurso ao
  arquivo da secção `# EXECUÇÃO` da app Streamlit.
- `tests/test_nicegui.py` confirma que dá as mesmas decisões que a app.

Vantagens face ao Streamlit: a página não volta a correr de cima a baixo a
cada clique; mapa Leaflet nativo (sem iframe); controlo total do aspecto.

## Correr

```bash
pip install -r nicegui_app/requirements.txt
cd nicegui_app && python main.py      # http://localhost:8080
```

`STORAGE_SECRET=<qualquer texto>` faz a app lembrar-se do aeródromo escolhido
entre visitas (guardado no browser de cada utilizador).

## Alojar (gratuito)

Hugging Face Spaces, tipo **Docker**, com o `Dockerfile` desta pasta (porta
7860). A app adormece sem uso e demora alguns segundos a acordar.
