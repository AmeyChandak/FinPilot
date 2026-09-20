import os
import json
import base64

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


# =========================================================
# OPENAI CLIENT
# =========================================================

api_key = os.getenv(
    "OPENAI_API_KEY"
)

if not api_key:

    raise RuntimeError(
        "OPENAI_API_KEY is missing from .env"
    )


client = OpenAI(
    api_key=api_key
)


MODEL = "gpt-5.6-luna"


# =========================================================
# STRUCTURED OUTPUT SCHEMA
# =========================================================

TRANSACTION_SCHEMA = {

    "type": "object",

    "properties": {

        "transactions": {

            "type": "array",

            "items": {

                "type": "object",

                "properties": {

                    "date": {
                        "type": "string"
                    },

                    "description": {
                        "type": "string"
                    },

                    "amount": {
                        "type": "number"
                    },

                    "type": {

                        "type": "string",

                        "enum": [
                            "income",
                            "expense"
                        ]

                    }

                },

                "required": [
                    "date",
                    "description",
                    "amount",
                    "type"
                ],

                "additionalProperties": False

            }

        }

    },

    "required": [
        "transactions"
    ],

    "additionalProperties": False

}


# =========================================================
# AI INSTRUCTIONS
# =========================================================

EXTRACTION_INSTRUCTIONS = """

You are FinPilot's financial document extraction engine.

Your task is to extract financial transactions from
the supplied financial document or image.

Extract ONLY transactions that are clearly visible
or explicitly stated.

DO NOT invent transactions.

For every transaction return:

1. date
2. description
3. amount
4. type

type must be either:

"income"

or

"expense"

IMPORTANT:

- Return amounts as positive numbers.
- The backend will convert expenses to negative values.
- Preserve the actual transaction amount.
- Do not confuse account balance with a transaction.
- Do not treat account numbers as transactions.
- Ignore page numbers.
- Ignore customer IDs.
- Ignore phone numbers.
- Ignore addresses.
- Ignore bank account numbers.
- Ignore headings.
- Ignore totals unless they represent an actual transaction.
- If a transaction is unclear, skip it.
- Do not provide financial advice.

If the document contains multiple pages,
extract transactions from all available pages.

"""


# =========================================================
# IMAGE → AI
# =========================================================

def extract_from_image(
    filepath
):

    with open(
        filepath,
        "rb"
    ) as image_file:

        image_bytes = (
            image_file.read()
        )

    encoded = base64.b64encode(
        image_bytes
    ).decode("utf-8")


    extension = os.path.splitext(
        filepath
    )[1].lower()


    if extension == ".png":

        mime_type = "image/png"

    elif extension == ".jpg":

        mime_type = "image/jpeg"

    else:

        mime_type = "image/jpeg"


    response = client.responses.create(

        model=MODEL,

        input=[

            {

                "role": "user",

                "content": [

                    {

                        "type":
                            "input_text",

                        "text":
                            EXTRACTION_INSTRUCTIONS

                    },

                    {

                        "type":
                            "input_image",

                        "image_url":
                            f"data:{mime_type};base64,{encoded}"

                    }

                ]

            }

        ],

        text={

            "format": {

                "type":
                    "json_schema",

                "name":
                    "financial_transactions",

                "schema":
                    TRANSACTION_SCHEMA,

                "strict":
                    True

            }

        }

    )


    return json.loads(
        response.output_text
    )


# =========================================================
# TEXT → AI
# =========================================================

def extract_from_text(
    text
):

    if not text.strip():

        raise ValueError(
            "No readable text was found."
        )


    # Prevent enormous accidental input
    text = text[:200000]


    response = client.responses.create(

        model=MODEL,

        input=[

            {

                "role": "user",

                "content": [

                    {

                        "type":
                            "input_text",

                        "text":
                            EXTRACTION_INSTRUCTIONS
                            +
                            "\n\nDOCUMENT CONTENT:\n"
                            +
                            text

                    }

                ]

            }

        ],

        text={

            "format": {

                "type":
                    "json_schema",

                "name":
                    "financial_transactions",

                "schema":
                    TRANSACTION_SCHEMA,

                "strict":
                    True

            }

        }

    )


    return json.loads(
        response.output_text
    )