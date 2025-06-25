from ayejax import find_shopify_reviews
from ayejax.codegen import BashCurlCode, PythonRequestsCode
from ayejax.logging import FileHandlerConfig, create_logger

logger = create_logger(
    name="ayejax",
    file_handler_config=FileHandlerConfig(
        directory=".",
    ),
)

candidates = find_shopify_reviews(
    "https://www.vitalproteins.com/products/collagen-gummies",
    logger=logger,
)

if not candidates:
    raise ValueError("No candidates found")

request = candidates[0].request

bash_code = BashCurlCode.from_request(request)
with open("new.sh", "w") as f:
    f.write(bash_code.render(caller_type="loop"))

python_code = PythonRequestsCode.from_request(request)
with open("new.py", "w") as f:
    f.write(python_code.render(caller_type="loop"))
