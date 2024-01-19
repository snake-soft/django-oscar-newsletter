from uuid import uuid4
from django.utils.text import slugify
from urllib.parse import urlparse
from apps.offer.slides import Slide
from ..models import Message, Article


class MessageGenerator:
    title = ''

    def __init__(self, request, offer, with_prices):
        self.request = request
        self.offer = offer
        self.with_prices = with_prices
        self.range = offer.benefit.range
        self.slides = Slide.objects.filter(rangeproduct__range=self.range)

    def attach_message(self, message):
        self._generate_articles(message)
        return message

    def generate(self, newsletter):
        message = self._generate_message(newsletter)
        self._generate_articles(message)
        return message

    def _generate_message(self, newsletter):
        slug = slugify(self.offer.name) + '_'
        suffix = 0
        while Message.objects.filter(
                newsletter=newsletter,
                slug=slug + str(suffix)):
            suffix += 1

        message = Message.objects.create(
            newsletter=newsletter,
            slug=str(uuid4()),
            title=self.offer.name,
        )
        return message

    def _get_image(self, slide):
        if slide.cached_slide:
            return slide.cached_slide
        return slide.image

    def _generate_articles(self, message):
        articles = []
        for slide in self.slides:
            image = self._get_image(slide)
            article = Article.objects.update_or_create(
                post=message,
                image=image,
                defaults={
                    'title': slide.get_title().replace('<br>', ' '),
                    'url': self.get_url(slide),
                    'text': '',
                }
            )[0]
            articles.append(article)
        return articles

    def get_url(self, slide):
        link = slide.get_link()
        if link:
            return self.absolute_url(slide.get_link())

    def absolute_url(self, url):
        is_absolute = bool(urlparse(url).netloc)
        if is_absolute:
            return url
        return self.request.build_absolute_uri(url)
