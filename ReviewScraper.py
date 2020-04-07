import json
import math
import re

import aiohttp
from bs4 import BeautifulSoup


class ReviewScraper:
    def __init__(self, business_id=0):
        # 예약자 리뷰 검색에 필요한 bookingBusinessId
        self.businessId = business_id
        self.bookingBusinessId = 0

        # 각 영역 별 최대 개수
        # 이 개수를 초과 시 API에서 정보가 없는 json 파일을 반환함.
        self.num_booking_display_per_page = 50
        self.num_blog_display_per_page = 50
        self.num_receipt_display_per_page = 100

        # 각 api 주소
        self.str_booking_url = "https://store.naver.com/sogum/api/bookingReviews?bookingBusinessId="
        self.str_blog_url = "https://store.naver.com/sogum/api/fsasReviews?businessId="
        self.str_receipt_url = "https://store.naver.com/sogum/api/receiptReviews?businessId="
        self.str_main_url = "https://store.naver.com/restaurants/detail?id="
        self.str_display_for_url = "&display="
        self.str_page_for_url = "&page="
        self.str_start_for_url = "&start="

        # 블로그 글에서 한글만 추출해내기 위한 정규표현식임.
        self.blog_extract_pattern = re.compile("[ㄱ-ㅎㅏ-ㅣ가-힣 ]+")
        self.blog_multi_space_pattern = re.compile("\s{2,}")
        self.bookingId_extract_pattern = re.compile("\"bookingBusinessId\":\"(?P<bookingBusinessId>\d+)\"")

    async def fetch(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as res:
                assert res.status == 200
                return await res.text()

    def get_max_loop_count(self, total, per_page):
        return int(math.ceil(total / per_page))

    def blog_subtract_by_regex(self, text):
        return re.sub(self.blog_multi_space_pattern, ' ', " ".join(self.blog_extract_pattern.findall(text)))

    # 네이버에서 예약이 가능한 가게는 bookingBusinessId를 가지고 있다.
    # 네이버에서, bookingBusinessId와 businessId는 개별적인 id이다. 값이 아예 다르다.
    # 따라서 bookingBusinessId를 조회해야만 예약자 리뷰를 조회할 수 있다.
    # bookingBusinessId를 조회할 마땅한 방법이나 API가 없다..
    # 고로 html 속에서 정규표현식으로 추출한다.
    async def get_booking_business_id(self, businessId):
        request_url = self.str_main_url + str(businessId)
        response = await self.fetch(request_url)
        if response is not None:
            # 정규 표현식으로 추출
            matched_group = self.bookingId_extract_pattern.search(response)
            # bookingBusinessId가 존재하는 경우
            if type(matched_group) is not None:
                # 정규표현식 그룹으로 추출
                bookingBusinessId = matched_group.group("bookingBusinessId")
                self.bookingBusinessId = bookingBusinessId
                # 반환
                return bookingBusinessId
        # 문제가 발생시 None 반환
        else:
            return None

    # 블로그, 카페 글들을 조회하는 메서드.
    # businessId를 기준으로 조회할 수 있다.
    # 예약자나 영수증 리뷰와는 다르게 start가 존재하고, 1부터 시작한다.
    # 글들의 개수 자체는 많으나, 조회할 수 있는 글의 개수는 한정적이다.
    # 글이 2천개가 있어도 100개 정도의 글만 조회 가능.
    # 따라서 maxItemCount 라는 항목을 이용해서 크롤링 해야 한다.
    async def get_blog_reviews(self, businessId, only_korean=False):
        num_start = 1
        request_url = self.str_blog_url \
                      + str(businessId) \
                      + self.str_start_for_url \
                      + str(num_start) \
                      + self.str_display_for_url \
                      + str(self.num_blog_display_per_page)
        response = await self.fetch(request_url)
        # Response가 제대로 온 경우
        if response is not None:
            # json으로 변환
            json_response = json.loads(response)
            try:
                num_max_item_count = int(json_response['maxItemCount'])
            except KeyError:
                return None
            if num_max_item_count > self.num_receipt_display_per_page:
                num_loop_count = self.get_max_loop_count(num_max_item_count, self.num_blog_display_per_page) - 1
                for num_i in range(1, num_loop_count):
                    # num_i * 페이지 수를 곱해서, start에 더한 주소로 get 요청을 보내야 한다.
                    # 1부터 50건을 조회했으므로 다음 start는 51, 101, 151 식임.
                    tmp_url = self.str_blog_url \
                              + str(businessId) \
                              + self.str_start_for_url \
                              + str(num_start + (num_i * self.num_blog_display_per_page)) \
                              + self.str_display_for_url \
                              + str(self.num_blog_display_per_page)
                    tmp_response = await self.fetch(tmp_url)
                    # Response가 제대로 온 경우
                    if tmp_response is not None:
                        tmp_json_response = json.loads(tmp_response)
                        json_response['items'] += tmp_json_response['items']
            for item in json_response['items']:
                tmp_blog_text = ""
                # 카페인 경우 무시, 경우의 수가 지나치게 많음..
                if item['typeName'] == "카페":
                    continue
                tmp_blog_url = item["url"]
                tmp_response = await self.fetch(tmp_blog_url)
                if tmp_response is None:
                    print("None detected")
                if tmp_response is not None:
                    soup = BeautifulSoup(tmp_response, 'html.parser')
                    # 스마트에디터 2버전 기준 컨테이너 클래스 내부의 텍스트 태그들 리스트를 select로 모음
                    tags = soup.select("body div.se-main-container p.se-text-paragraph")
                    # 스마트에디터 3버전 기준 텍스트 태그들 리스트, 기존 tags 길이가 0인 경우(없는 경우) 새로 찾음
                    if tags is None or len(tags) == 0:
                        tags = soup.select("body div.se_component_wrap p.se_textarea")
                    # 구버전인 경우 postViewArea, viewTypeSelector 로 시도
                    if tags is None or len(tags) == 0:
                        tags = soup.select('body div#postViewArea p')
                    if tags is None or len(tags) == 0:
                        tags = soup.select('body div#viewTypeSelector p')
                    # 모두 다 아닌 경우 오류이므로 무시함
                    if tags is None or len(tags) == 0:
                        continue
                    # 블로그에서 텍스트만 띄어쓰기로 추출 (각 텍스트가 모두 p나 span에 들어있음)
                    for children_tag in tags:
                        tmp_blog_text += str(children_tag.text) + ' '
                    # 정규 표현식으로 한글만 추출 (필요에 따라 매개변수 사용)
                    if only_korean:
                        item["subText"] = self.blog_subtract_by_regex(tmp_blog_text)
                    else:
                        item["subText"] = tmp_blog_text
            return json_response

        else:
            return None

    # 영수증 리뷰 크롤러이다.
    # businessId를 기준으로 반환 결과를 얻을 수 있다.
    # total을 기준으로 전체 크롤링이 가능하다. 물론 반복적인 조회가 필요.
    async def get_receipt_reviews(self, businessId):
        # 1부터 시작함.
        num_page = 1
        request_url = self.str_receipt_url \
                      + str(businessId) \
                      + self.str_page_for_url \
                      + str(num_page) \
                      + self.str_display_for_url \
                      + str(self.num_receipt_display_per_page)
        response = await self.fetch(request_url)

        if response is not None:
            json_response = json.loads(response)
            try:
                num_total_count = int(json_response['total'])
            except KeyError:
                return None
            if num_total_count == 0:
                return None
            elif num_total_count > self.num_receipt_display_per_page:
                num_loop_count = self.get_max_loop_count(num_total_count, self.num_receipt_display_per_page) + 1
                for num_i in range(1, num_loop_count):
                    tmp_url = "https://store.naver.com/sogum/api/receiptReviews?businessId=" \
                              + str(businessId) \
                              + self.str_page_for_url \
                              + str(num_page + num_i) \
                              + self.str_display_for_url \
                              + str(self.num_receipt_display_per_page)
                    tmp_response = await self.fetch(tmp_url)
                    if tmp_response is not None:
                        tmp_json_response = json.loads(tmp_response)
                        json_response['items'] += tmp_json_response['items']
            return json_response
        else:
            return None

    # 예약 리뷰를 조회하는 메서드.
    # bookingBusinessId를 기준으로 리뷰를 조회할 수 있다.
    # bookingBusinessId를 찾는 것은 별도의 함수로 위에서 구현하도록 한다.
    async def get_booking_reviews(self, bookingBusinessId):
        # 예약 리뷰 page 파라미터는 0부터 시작한다.
        num_page = 0
        request_url = self.str_booking_url \
                      + str(bookingBusinessId) \
                      + self.str_page_for_url \
                      + str(num_page) \
                      + self.str_display_for_url \
                      + str(self.num_booking_display_per_page)
        response = await self.fetch(request_url)

        if response is not None:
            json_response = json.loads(response)
            try:
                num_selected_total_count = int(json_response['selectedTotal'])
            except KeyError:
                return None
            if num_selected_total_count > self.num_blog_display_per_page:
                num_loop_count = self.get_max_loop_count(num_selected_total_count, self.num_booking_display_per_page)
                for num_i in range(1, num_loop_count):
                    tmp_url = self.str_booking_url \
                              + str(bookingBusinessId) \
                              + self.str_page_for_url \
                              + str(num_i) \
                              + self.str_display_for_url \
                              + str(self.num_booking_display_per_page)
                    tmp_response = await self.fetch(tmp_url)
                    if tmp_response is not None:
                        tmp_json_response = json.loads(tmp_response)
                        json_response['items'] += tmp_json_response['items']
            return json_response
        else:
            return None
