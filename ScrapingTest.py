import asyncio

from ReviewScraper import ReviewScraper

id_list = []
crawler = ReviewScraper()


async def main():
    for businessId in id_list:
        await crawler.get_all_by_business_id(str(businessId))


asyncio.run(main())
