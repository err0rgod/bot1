# Base image: AWS Lambda Python 3.12 (Amazon Linux 2023)
FROM public.ecr.aws/lambda/python:3.12

# Install dependencies required for C extensions (lxml, Pillow)
RUN dnf install -y \
    gcc \
    gcc-c++ \
    libxml2-devel \
    libxslt-devel \
    libjpeg-turbo-devel \
    zlib-devel \
    && dnf clean all \
    && rm -rf /var/cache/dnf

# Runtime environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    NLTK_DATA=${LAMBDA_TASK_ROOT}/nltk_data

# Copy requirements
COPY requirements.txt ${LAMBDA_TASK_ROOT}/

# Install python dependencies into Lambda task root
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Pre-download NLTK data to prevent runtime downloads / sandbox permission issues
RUN python -m nltk.downloader -d ${LAMBDA_TASK_ROOT}/nltk_data punkt stopwords || true

# Copy application code into Lambda task root
COPY db/ ${LAMBDA_TASK_ROOT}/db/
COPY llm/ ${LAMBDA_TASK_ROOT}/llm/
COPY scraper/ ${LAMBDA_TASK_ROOT}/scraper/
COPY notifications/ ${LAMBDA_TASK_ROOT}/notifications/
COPY lambdaFunction.py ${LAMBDA_TASK_ROOT}/

# Lambda Handler entrypoint
CMD [ "lambdaFunction.lambda_handler" ]