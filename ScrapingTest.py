import asyncio

from ReviewScraper import ReviewScraper

id_list = []


async def main():
    for businessId in id_list:
        crawler = ReviewScraper()
        await crawler.get_all_by_business_id(str(businessId))


asyncio.run(main())
