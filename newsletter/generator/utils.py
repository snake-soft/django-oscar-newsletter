from django.utils.text import slugify
from urllib.parse import urlparse
from ..models import Message, Article


class MessageGenerator:
    title = ''

    def __init__(self, request, offer, newsletter, with_prices):
        self.request = request
        self.offer = offer
        self.newsletter = newsletter
        self.with_prices = with_prices
        self.range = offer.benefit.range
        self.range_products = self.range.rangeproduct_set.filter(
            cached_slide__isnull=False
        )

    def generate(self):
        message = self._generate_message()
        self._generate_articles(message)
        return message

    def _generate_message(self):
        message = Message.objects.get_or_create(
            newsletter=self.newsletter,
            slug=slugify(self.offer.name),
            defaults={
                'title': self.offer.name,
            }
        )[0]
        return message

    def _generate_articles(self, message):
        articles = []
        for range_product in self.range_products:
            image = range_product.cached_slide if self.with_prices \
                else range_product.image.file
            article = Article.objects.update_or_create(
                post=message,
                image=image,
                defaults={
                    'title': range_product.get_title(),
                    #'sortorder': range_product.display_order,
                    'url': self.absolute_url(range_product.get_link()),
                    'text': '',
                }
            )[0]
            articles.append(article)
        return articles

    def absolute_url(self, url):
        is_absolute = bool(urlparse(url).netloc)
        if is_absolute:
            return url
        return self.request.build_absolute_uri(url)
