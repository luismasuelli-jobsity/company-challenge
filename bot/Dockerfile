FROM python:3
ENV FINBOT_USERNAME=finbot
ENV FINBOT_PASSWORD="p455w0rd"
ENV FINBOT_ROOMS=""
ENV FINBOT_HOST=""
# The bot will only involve a single script, with
# one dependencies: "aiohttp" library.
WORKDIR /
COPY requirements.txt /
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
COPY bot.py /
CMD python bot.py