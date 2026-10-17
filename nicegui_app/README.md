# Interface NiceGUI (principal)

A interface principal da app, publicada em https://gamet-vfr-app.onrender.com/.
A app Streamlit (`app.py`) continua publicada como reserva.

- O motor é o mesmo: `motor.py` executa as secções de `app.py` que os testes
  usam (parser, geometria, decisão, PDF, componentes HTML) e a secção de rede.
  Uma correcção no `app.py` vale para as duas interfaces.
- `main.py` tem só a interface. A análise é `analisar_gamet()` do motor, a
  mesma que a app Streamlit usa.
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

Render, serviço web gratuito (Docker), ligado directamente ao GitHub — cada
push no ramo `main` volta a publicar. Não é preciso guardar
nenhuma chave no repositório.

- Dockerfile Path: `nicegui_app/Dockerfile` · Docker Build Context: `.` (raiz)
- O Render define a porta (`PORT`); a app usa-a.
- Plano gratuito: adormece após 15 min sem uso e demora ~1 min a acordar.
  (O Hugging Face Spaces passou a exigir plano pago para apps Docker.)
