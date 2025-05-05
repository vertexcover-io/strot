import os

import ayejax

output = ayejax.find(
    "https://www.swiggy.com/instamart/category-listing?categoryName=Fresh+Vegetables&custom_back=true&taxonomyType=Speciality+taxonomy+1",
    "all the listed vegetables",
    llm_client=ayejax.llm.LLMClient(provider="openai", model="gpt-4o", api_key=os.getenv("OPENAI_API_KEY")),
)
for candidate in output.candidates:
    print("===============================================")
    print(candidate.request.as_curl_command(format="cmd"))
    print("===============================================")
