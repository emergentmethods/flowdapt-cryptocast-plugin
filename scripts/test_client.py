from flowdapt_sdk import FlowdaptSDK
import asyncio

"""
Example of how to use the FlowdaptSDK to run a workflow and obtain the
result.

This exact code can be placed inside `populate_indicators` to get a prediction
and use it in entry/exit critera.
"""

async def run_flowdapt_workflow(
    workflow_name: str,
    payload: dict
):

    async with FlowdaptSDK("http://localhost:8080", timeout=20) as client:
        response = await client.workflows.run_workflow(
            workflow_name,
            input=payload
        )

    return response.result


def main():
    payload = {"asset": "ETH-USDT"}
    response = asyncio.run(run_flowdapt_workflow("predict", payload))
    print(response)


if __name__ == '__main__':
    main()
