import asyncio
import json

from ReviewScraper import ReviewScraper

businessId = 0


async def save_json_file(json_data, file_loc, encoding="utf-8", mode='w+'):
    with open(file_loc, encoding='utf-8', mode='w+') as file:
        file.write(json.dumps(json_data, ensure_ascii=False))
        file.close()


async def main():
    crawler = ReviewScraper()

    bookingBusinessId = await crawler.get_booking_business_id(businessId)
    booking_reviews = await crawler.get_booking_reviews(bookingBusinessId)
    blog_reviews = await crawler.get_blog_reviews(businessId)
    receipt_reviews = await crawler.get_receipt_reviews(businessId)

    booking_loc = "bookingReviews/" + str(businessId) + ".json"
    blog_loc = "blogReviews/" + str(businessId) + ".json"
    receipt_loc = "receiptReviews/" + str(businessId) + ".json"

    await save_json_file(booking_reviews, booking_loc)
    await save_json_file(blog_reviews, blog_loc)
    await save_json_file(receipt_reviews, receipt_loc)


asyncio.run(main())
