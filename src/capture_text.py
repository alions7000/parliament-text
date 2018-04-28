from .utils import args, logger
from .parse_text import transcript

from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import Select

import sys
from time import sleep
import os
import re
import requests


# TODO: what about evidence that doesn't form part of an inquiry: http://www.parliament.uk/business/committees/committees-a-z/lords-select/ai-committee/publications/
# TODO: go straight to the Committee's Publications page. Then look for "Oral and written evidence is on the relevant inquiry pages."
# TODO: need to drill down through HTML pages too and find unstructured oral evidence e.g. http://www.parliament.uk/business/committees/committees-a-z/commons-select/administration-committee/inquiries/parliament-2010/induction-arrangements-for-new-members-of-parliament/


class Downloader(object):
    """Download full or partial Parliamentary committee transcript records"""
    def __init__(self):
        self.committees_page = 'http://www.parliament.uk/business/committees/committees-a-z/'
        self.browser = webdriver.Firefox()
        self.storage_path = args.storage


    def committees_urls_list(self):
        """A-to-Z listing of all parliamentary committees

        :return: list of URLs representing the homepage of each committee
        """
        self.browser.set_page_load_timeout(30)
        self.browser_get(self.committees_page)

        xp_committees_list = '//div[@class="a-to-z-listing"]/ul[@class="square-bullets-a-to-z"]/li/h3/a'
        urls = [x.get_attribute('href') for x in
                self.browser.find_elements_by_xpath(xp_committees_list)]
        return urls

    def capture_committee_documents(self, committee_url):
        """Crawl relevant pages of the committee to find transcript documents

        :param committee_url: URL of the committee homepage
        """
        self.browser.set_page_load_timeout(10)
        logger.warning('Starting new committee: ' + committee_url)


        """Sometimes there's no Inquiries selection, and we go 
        straight to Publications, e.g.: 
        http://www.parliament.uk/business/committees/committees-a-z/commons-select/armed-forces-bill-committee-2015/"""

        self.browser_get(committee_url)
        pubs_links = self.browser.find_elements_by_link_text('Publications')
        if len(pubs_links) > 0 and committee_url in pubs_links[0].get_attribute(
                'href'):
            publications_url = pubs_links[0].get_attribute('href')
            self.crawl_publications_section(publications_url)
        else:
            logger.warning(
                "No Top-Level Publications Link for this committee: "
                + committee_url)

        self.browser_get(committee_url) # go back to the committee homepage
        inquiries_links = self.browser.find_elements_by_partial_link_text(
            'Inquiries')
        if len(inquiries_links) > 0 and committee_url in inquiries_links[
            0].get_attribute('href'):
            inquiries_url = inquiries_links[0].get_attribute('href')
            logger.info("Processing all inquiries: " + inquiries_url)
            self.crawl_inquiries_section(inquiries_url)
        else:
            logger.warning("No Inquiries for this committee: " + committee_url)



    def crawl_publications_section(self, publications_url):
        """Download from the top-level Publications section

        Iterate through selections on the 'Parliament Year Picker'
        drop-down to reveal lists of Publications, and download transcripts in
        each section found.
        :param publications_url: URL front page for top-level Publications link
        """
        self.browser_get(publications_url)
        # handle the top-level Publications page. Firstly, take any oral
        # evidence links seen on the first Publications page.
        self.capture_oral_evidence_urls_from_current_page()
        # next, if there's a drop-down instead, iterate through the
        # options to take any oral evidence links that
        # are available there
        try:
            sessions_filter = Select(
                self.browser.find_element_by_class_name('ctlSession'))
            all_options = [pf.text for pf in sessions_filter.options]
            # before iterating through the filter options,
            # just take the top-level URLs listing
            xp_publication_items = '//ul[@id="publication-items"]/li/a'
            urls = [x.get_attribute('href') for x in
                    self.browser.find_elements_by_xpath(
                        xp_publication_items)]
            for publications_filter_option in all_options:
                sessions_filter = Select(
                    self.browser.find_element_by_class_name('ctlSession'))
                sessions_filter.select_by_visible_text(
                    publications_filter_option)
                xp_submit_button = '//input[@class="ctlSubmit"]'
                go_button = self.browser.find_element_by_xpath(xp_submit_button)
                go_button.submit()
                urls = urls + [x.get_attribute('href') for x in
                               self.browser.find_elements_by_xpath(
                                   xp_publication_items)]
        except:
            logger.info('no publications drop-down processed')


    def crawl_inquiries_section(self, inquiries_url):
        """Locate all inquiries listed in the inquiries section

        Iterate through selections on the 'Parliament Year Picker'
        drop-down to reveal lists of inquiries, and download transcripts in
        each inquiry found.
        :param inquiries_url: URL front page for all Inquiries
        """
        self.browser_get(inquiries_url)
        inquiries_filter = Select(
            self.browser.find_element_by_class_name('parliamentYearPicker'))
        all_options = [ifo.text for ifo in inquiries_filter.options]
        urls = []
        for inquiries_filter_option in all_options:
            inquiries_filter = Select(
                self.browser.find_element_by_class_name('parliamentYearPicker'))
            inquiries_filter.select_by_visible_text(inquiries_filter_option)
            # current inquiries list format:
            xp_current_inquiries = '//ul[@id="inquiries"]/li/a'
            urls = urls + [x.get_attribute('href') for x in
                           self.browser.find_elements_by_xpath(
                               xp_current_inquiries)]
            # historical inquiries list format:
            xp_historical_inquiries = '//div[@class="a-to-z-listing"]/ul[@class="square-bullets-a-to-z"]/li/h3/a'
            urls = urls + [x.get_attribute('href') for x in
                           self.browser.find_elements_by_xpath(
                               xp_historical_inquiries)]

        logger.info("Found %i inquiries" % len(urls))
        for i, url in enumerate(urls):
            self.crawl_inquiry(url)
        pass



    def crawl_inquiry(self, inquiry_url):
        """Locate and download all transcripts for a certain inquiry

        Crawl pages starting at inquiry_url and download transcript documents
        :param inquiry_url: starting point for crawling
        """
        self.browser.set_page_load_timeout(60)
        logger.info("Starting inquiry: %s" % inquiry_url)
        self.browser_get(inquiry_url)
        pubs_links = self.browser.find_elements_by_link_text('Publications')
        if len(pubs_links) > 0:
            publications_url = pubs_links[0].get_attribute('href')
            self.browser_get(publications_url)
            logger.info(
                "Found a Publications page for the inquiry: %s" % inquiry_url)
        else:
            logger.info(
                "Found no Publications page for the inquiry: %s " % inquiry_url)
        # if there's a drop-down for 'publications types' then
        # select Oral Evidence (otherwise, just use the full list of
        # URLs and find the oral evidence ones
        try:
            publications_type_filter = Select(
                self.browser.find_element_by_class_name('ctlType'))
            if 'Oral evidence' in [pt.text for pt in
                                   publications_type_filter.options]:
                publications_type_filter.select_by_visible_text('Oral evidence')
                xp_submit_button = '//input[@class="ctlSubmit"]'
                self.browser.find_element_by_xpath(xp_submit_button).submit()
        except:
            # no problem if there isn't a 'publications type' filter
            # for this inquiry's publications:
            # we just continue to take a the full unfiltered list
            pass
        self.capture_oral_evidence_urls_from_current_page()
        pass


    def browser_get(self, url):
        """Access page URL in browser"""
        retries = 0
        success = False
        while (not success) and (retries <= 10):
            try:
                self.browser.get(url)
                success = True
            except TimeoutException as e:
                wait = (retries ^ 3) * 20
                logger.warning(e)
                logger.info('URL: %s' % url)
                logger.info('Waiting %s secs and re-trying...' % wait)
                sleep(wait)
                retries += 1
        if retries > 10:
            logger.error('Download repeatedly failed: %s', url)
            sys.exit('Download repeatedly failed: %s' % url)

    def capture_oral_evidence_urls_from_current_page(self):
        """Seek and download all oral evdience URLs on the current web page
        """
        stale_error = False
        for x in range(0, 10):
            try:
                all_urls = [x.get_attribute('href') for x in
                            self.browser.find_elements_by_class_name(
                                'document-title') + \
                            self.browser.find_elements_by_class_name(
                                'document')]
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
            self.download_and_process_document(u, f)

    def download_and_process_document(self, url, filename):
        """Download and store a HTML or PDF document

        :param url: URL of the document
        :param filename: filesystem path where we wish to store the document
        :return:
        """
        logger.info("Document: " + url)
        retries = 0
        success = False
        filetype = filename.split('.')[1]
        while (not success) and (retries <= 10):
            try:
                r = requests.get(url, timeout=20)
                source_document_locations = {'url_index':
                                                 self.browser.current_url,
                                             'url_document': url}
                if filetype == 'html':
                    with open(os.path.join(self.storage_path,
                                           filename),'w') as f:
                        # address an apparent problem with encoding
                        # on the Parliament html pages
                        html_text = r.content.decode('utf-8')
                        f.write(html_text)

                    current_transcript = transcript(html_text,
                                                    source_document_locations,
                                                    filename)
                    current_transcript.process_raw_html(parse_to_json=False)
                elif filetype == 'pdf':
                    with open(os.path.join(self.storage_path, filename),
                              'wb') as f:
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


def page_not_found(browser):
    is_not_found_warning = browser.find_element_by_name(
        'title').get_attribute(
        'content') == 'Page cannot be found'
    is_server_error_warning = browser.find_element_by_tag_name(
        'h1').text == "Server Error"
    return is_not_found_warning or is_server_error_warning
