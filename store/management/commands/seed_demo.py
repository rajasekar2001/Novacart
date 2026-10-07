from django.core.management.base import BaseCommand
from store.models import Category,Product
class Command(BaseCommand):
    help='Create demo store products'
    def handle(self,*args,**kwargs):
        cat,_=Category.objects.get_or_create(name='Essentials',slug='essentials')
        rows=[('Aurora Headphones','aurora-headphones','Immersive wireless audio with adaptive noise control.',7999,18),('Terra Bottle','terra-bottle','Insulated stainless steel bottle made for daily adventures.',1299,30),('Halo Desk Lamp','halo-desk-lamp','Minimal dimmable lamp with warm and cool light modes.',3499,12),('Nomad Backpack','nomad-backpack','Water-resistant everyday carry with a padded laptop sleeve.',4599,20),('Drift Sneakers','drift-sneakers','Lightweight everyday sneakers with a breathable upper.',5299,15),('Still Ceramic Set','still-ceramic-set','A calm, hand-finished ceramic set for slow mornings.',2499,9)]
        for name,slug,description,price,stock in rows: Product.objects.update_or_create(slug=slug,defaults={'category':cat,'name':name,'description':description,'price':price,'stock':stock,'active':True})
        self.stdout.write(self.style.SUCCESS('Demo products created.'))
