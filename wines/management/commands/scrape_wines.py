from django.core.management.base import BaseCommand
from wines.views import scrape_vinoteca, scrape_ewine, scrape_mundo_vino

class Command(BaseCommand):
    help = 'Comando para iniciar el scraping de vinotecas.'

    def handle(self, *args, **options):
        self.stdout.write("Iniciando el scraping de la vinoteca...")
        result_vinoteca = scrape_vinoteca()
        self.stdout.write(f"Scraping de la vinoteca completado: {result_vinoteca}")

        self.stdout.write("Iniciando el scraping de eWine...")
        result_ewine = scrape_ewine()
        self.stdout.write(f"Scraping de eWine completado: {result_ewine}")

        self.stdout.write("Iniciando el scraping de Mundo Vino...")
        result_mundo_vino = scrape_mundo_vino()
        self.stdout.write(f"Scraping de Mundo Vino completado: {result_mundo_vino}")