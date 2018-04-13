

from .utils import args, logger, browser_get
from .parse_text import transcript

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.support.ui import Select

import sys
from time import sleep
import os
import re
import requests


class Downloader(object):
    def __init__(self):
        self.committees_page = 'http://www.parliament.uk/business/committees/committees-a-z/'
        self.browser = webdriver.Firefox()
        self.storage_path = args.storage


    def get_committees_urls(self):
        self.browser.set_page_load_timeout(30)
        browser_get(self.browser, self.committees_page)

        urls = [x.get_attribute('href') for x in
                self.browser.find_elements_by_xpath(
                    '//div[@class="a-to-z-listing"]/ul[@class="square-bullets-a-to-z"]/li/h3/a')]
        return urls

    def process_committee(self, committee_url):
        self.browser.set_page_load_timeout(10)
        logger.warning('Starting new committee: ' + committee_url)
        # TODO: go straight to the Committee's Publications page. Then look for "Oral and written evidence is on the relevant inquiry pages."
        browser_get(self.browser, committee_url)
        pubs_links = self.browser.find_elements_by_link_text('Publications')
        if len(pubs_links) > 0 and committee_url in pubs_links[0].get_attribute(
                'href'):
            publications_url = pubs_links[0].get_attribute('href')
            browser_get(self.browser, publications_url)

            if not self.page_not_found(self.browser):
                # handle the top-level Publications page. Firstly, take any oral
                # evidence links seen on the first Publications page.
                self.grab_all_oral_evidence_urls()
                # next, if there's a drop-down instead, iterate through the options
                # to take any oral evidence links that are available there
                try:
                    sessions_filter = Select(
                        self.browser.find_element_by_class_name('ctlSession'))
                    all_options = [pf.text for pf in sessions_filter.options]
                    # before iterating through the filter options, just take the top-level URLs listing
                    urls = [x.get_attribute('href') for x in
                            self.browser.find_elements_by_xpath(
                                '//ul[@id="publication-items"]/li/a')]
                    for publications_filter_option in all_options:
                        sessions_filter = Select(
                            self.browser.find_element_by_class_name('ctlSession'))
                        sessions_filter.select_by_visible_text(
                            publications_filter_option)
                        go_button = self.browser.find_element_by_xpath(
                            '//input[@class="ctlSubmit"]')
                        go_button.submit()
                        urls = urls + [x.get_attribute('href') for x in
                                       self.browser.find_elements_by_xpath(
                                           '//ul[@id="publication-items"]/li/a')]
                except:
                    logger.info('no publications drop-down processed')
        else:
            logger.warning(
                "No Publications for this committee: " + committee_url)

        # No, sometimes there's no Inquiries selection, but we go straight to Publications http://www.parliament.uk/business/committees/committees-a-z/commons-select/armed-forces-bill-committee-2015/

        # # Make browser wait until page fully loaded:-
        # _ = WebDriverWait(browser, 10).until(
        #     EC.presence_of_element_located(
        #         (By.PARTIAL_LINK_TEXT, "Publications"))
        # )
        browser_get(self.browser, committee_url)
        # try:
        inquiries_links = self.browser.find_elements_by_partial_link_text(
            'Inquiries')
        if len(inquiries_links) > 0 and committee_url in inquiries_links[
            0].get_attribute('href'):
            inquiries_url = inquiries_links[0].get_attribute('href')
            logger.info("Processing all inquiries: " + inquiries_url)
            self.process_inquiries(self.browser, inquiries_url)
        else:
            logger.warning("No Inquiries for this committee: " + committee_url)

            # except:
            #     logger.warning("NO INQUIRIES FOUND FOR COMMITTEE: " + committee_url)

    #         TODO: what about evidence that doesn't form part of an inquiry: http://www.parliament.uk/business/committees/committees-a-z/lords-select/ai-committee/publications/




    def process_inquiries(self, browser, inquiries_url):
        # try:
        browser_get(self.browser, inquiries_url)
        # except:
        #     logger.warning('Could not Inquiries page')

        inquiries_filter = Select(
            self.browser.find_element_by_class_name('parliamentYearPicker'))
        all_options = [ifo.text for ifo in inquiries_filter.options]
        urls = []
        for inquiries_filter_option in all_options:
            inquiries_filter = Select(
                self.browser.find_element_by_class_name('parliamentYearPicker'))
            inquiries_filter.select_by_visible_text(inquiries_filter_option)
            # current inquiries list format:
            urls = urls + [x.get_attribute('href') for x in
                           self.browser.find_elements_by_xpath(
                               '//ul[@id="inquiries"]/li/a')]
            # historical inquiries list format:
            urls = urls + [x.get_attribute('href') for x in
                           self.browser.find_elements_by_xpath(
                               '//div[@class="a-to-z-listing"]/ul[@class="square-bullets-a-to-z"]/li/h3/a')]

        logger.info("Found %i inquiries" % len(urls))
        for url in urls:
            self.process_inquiry(browser, url)
            # self.browser.get(home_url)
        # self.browser.get(inquiries_url)      # go back to the Inquiries front page, ready to choose a new filter optio
        pass

    def page_not_found(self, browser):
        is_not_found_warning = self.browser.find_element_by_name(
            'title').get_attribute(
            'content') == 'Page cannot be found'
        is_server_error_warning = self.browser.find_element_by_tag_name(
            'h1').text == "Server Error"
        return is_not_found_warning or is_server_error_warning

    def process_inquiry(self, browser, inquiry_url):
        self.browser.set_page_load_timeout(60)
        logger.info("Starting inquiry: %s" % inquiry_url)
        browser_get(self.browser, inquiry_url)
        pubs_links = self.browser.find_elements_by_link_text('Publications')
        if len(pubs_links) > 0:
            publications_url = pubs_links[0].get_attribute('href')
            browser_get(self.browser, publications_url)
            logger.info(
                "Found a Publications page for the inquiry: %s" % inquiry_url)
        else:
            logger.info(
                "Found no Publications page for the inquiry: %s " % inquiry_url)
        # TODO: need to drill down through HTML pages too and find unstructured oral evidence e.g. http://www.parliament.uk/business/committees/committees-a-z/commons-select/administration-committee/inquiries/parliament-2010/induction-arrangements-for-new-members-of-parliament/
        # if there's a drop-down for 'publications types' then select Oral Evidence
        # (otherwise, just use the full list of URLs and find the oral evidence ones
        try:
            publications_type_filter = Select(
                self.browser.find_element_by_class_name('ctlType'))
            if 'Oral evidence' in [pt.text for pt in
                                   publications_type_filter.options]:
                publications_type_filter.select_by_visible_text('Oral evidence')
                self.browser.find_element_by_xpath(
                    '//input[@class="ctlSubmit"]').submit()
        except:
            # no problem if there isn't a 'publications type' filter for this inquiry's publications:
            # we just continue to take a the full unfiltered list
            pass
        self.grab_all_oral_evidence_urls()
        pass

    def grab_all_oral_evidence_urls(self):
        # # try a verbose approach instead of list comprehension to avoid StaleElementReferenceException
        stale_error = False
        for x in range(0, 10):
            try:
                all_urls = [x.get_attribute('href') for x in
                            self.browser.find_elements_by_class_name(
                                'document-title') + \
                            self.browser.find_elements_by_class_name('document')]
                stale_error = False
            except StaleElementReferenceException:
                stale_error = True
            if stale_error:
                sleep(2)
            else:
                break
        logger.info("Found %i reports etc URLs" % len(all_urls))
        oral_urls = [x for x in all_urls if
                     re.match(r'.*oral/\d+.(html|pdf)$', x)]
        logger.info("Found %i oral evidence URLs" % len(oral_urls))

        for u in oral_urls:
            f = u.split('/')[-1]
            self.download_page(u, f)

    def download_page(self, url, filename):
        logger.info("Document: " + url)
        retries = 0
        success = False
        filetype = filename.split('.')[1]
        while (not success) and (retries <= 10):
            try:
                r = requests.get(url, timeout=20)
                urls_dict = {'url_index': self.browser.current_url, 'url_link': url}
                if filetype == 'html':
                    with open(os.path.join(self.storage_path, filename),'w') as f:
                        html_text = r.content.decode('utf-8')
                        f.write(html_text)  # address an apparent problem with encoding on the Parliament html pages

                    current_transcript = transcript(html_text, urls_dict, filename)
                    current_transcript.process_and_save()
                elif filetype == 'pdf':
                    with open(os.path.join(self.storage_path, filename), 'wb') as f:
                        f.write(r.content)
                else:
                    logger.error('Unknown filetype: %s, %s' % (url, filename))
                success = True
            except requests.exceptions.RequestException as e:
                wait = (retries ^ 3) * 20
                logger.warning(e)
                logger.info('URL: %s' % url)
                logger.info('Waiting %s secs and re-trying...' % wait)
                sleep(wait)
                retries += 1
        if retries > 10:
            logger.error('Download repeatedly failed: %s', url)
            sys.exit('Download repeatedly failed: %s' % url)




