FROM mcr.microsoft.com/playwright/python:v1.60.0-jammy

# Install shell2telegram
ADD https://github.com/msoap/shell2telegram/releases/download/v1.10.0/shell2telegram_1.10.0_linux_amd64.tar.gz /tmp/s2t.tar.gz
RUN tar -C /usr/local/bin -xzf /tmp/s2t.tar.gz shell2telegram && rm /tmp/s2t.tar.gz

WORKDIR /app

# Copy requirements and install
# Note: Playwright image already has browsers installed for its version
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Ensure scripts are executable
RUN chmod +x parking.sh telegram_notify.py

# Environment variables for shell2telegram
ENV TB_TOKEN=""

# Command to run shell2telegram
ENTRYPOINT ["shell2telegram"]
CMD ["-log-commands", "-persistent-users", "/parking:vars=WHEN", "/bin/sh -c \"./parking.sh $WHEN\""]
