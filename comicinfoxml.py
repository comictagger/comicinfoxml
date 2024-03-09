"""A class to encapsulate ComicRack's ComicInfo.xml data."""
# Copyright 2012-2014 ComicTagger Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from collections import OrderedDict
from typing import Any
from typing import TYPE_CHECKING

from comicapi import utils
from comicapi.genericmetadata import GenericMetadata
from comicapi.genericmetadata import ImageMetadata
from comicapi.metadata import Metadata

if TYPE_CHECKING:
    from comicapi.archivers import Archiver

logger = logging.getLogger(f'comicapi.metadata.{__name__}')


class ComicInfoXml(Metadata):
    enabled = True

    short_name = 'cix'

    def __init__(self, version: str) -> None:
        super().__init__(version)

        self.file = 'ComicInfo.xml'
        self.supported_attributes = {
            'series',
            'issue',
            'issue_count',
            'title',
            'volume',
            'genres',
            'description',
            'notes',
            'alternate_series',
            'alternate_number',
            'alternate_count',
            'story_arcs',
            'series_groups',
            'publisher',
            'imprint',
            'day',
            'month',
            'year',
            'language',
            'web_link',
            'format',
            'manga',
            'black_and_white',
            'maturity_rating',
            'critical_rating',
            'scan_info',
            'tags',
            'pages',
            'pages.bookmark',
            'pages.double_page',
            'pages.height',
            'pages.image_index',
            'pages.size',
            'pages.type',
            'pages.width',
            'page_count',
            'characters',
            'teams',
            'locations',
            'credits',
            'credits.person',
            'credits.role',
        }

    def supports_credit_role(self, role: str) -> bool:
        return role.casefold() in self._get_parseable_credits()

    def supports_metadata(self, archive: Archiver) -> bool:
        return archive.supports_files()

    def has_metadata(self, archive: Archiver) -> bool:
        return (
            self.supports_metadata(archive)
            and self.file in archive.get_filename_list()
            and self._validate_bytes(archive.read_file(self.file))
        )

    def remove_metadata(self, archive: Archiver) -> bool:
        return self.has_metadata(archive) and archive.remove_file(self.file)

    def get_metadata(self, archive: Archiver) -> GenericMetadata:
        if self.has_metadata(archive):
            metadata = archive.read_file(self.file) or b''
            if self._validate_bytes(metadata):
                return self._metadata_from_bytes(metadata)
        return GenericMetadata()

    def get_metadata_string(self, archive: Archiver) -> str:
        if self.has_metadata(archive):
            return ET.tostring(ET.fromstring(archive.read_file(self.file)), encoding='unicode', xml_declaration=True)
        return ''

    def set_metadata(self, metadata: GenericMetadata, archive: Archiver) -> bool:
        if self.supports_metadata(archive):
            xml = b''
            if self.has_metadata(archive):
                xml = archive.read_file(self.file)
            return archive.write_file(self.file, self._bytes_from_metadata(metadata, xml))
        logger.warning('Archive (%s) does not support %s metadata', archive.name(), self.name())
        return False

    def name(self) -> str:
        return 'Comic Info XML'

    @classmethod
    def _get_parseable_credits(cls) -> list[str]:
        parsable_credits: list[str] = []
        parsable_credits.extend(GenericMetadata.writer_synonyms)
        parsable_credits.extend(GenericMetadata.penciller_synonyms)
        parsable_credits.extend(GenericMetadata.inker_synonyms)
        parsable_credits.extend(GenericMetadata.colorist_synonyms)
        parsable_credits.extend(GenericMetadata.letterer_synonyms)
        parsable_credits.extend(GenericMetadata.cover_synonyms)
        parsable_credits.extend(GenericMetadata.editor_synonyms)
        parsable_credits.extend(GenericMetadata.translator_synonyms)
        return parsable_credits

    def _metadata_from_bytes(self, string: bytes) -> GenericMetadata:
        root = ET.fromstring(string)
        return self._convert_xml_to_metadata(root)

    def _bytes_from_metadata(self, metadata: GenericMetadata, xml: bytes = b'') -> bytes:
        root = self._convert_metadata_to_xml(metadata, xml)
        return ET.tostring(root, encoding='utf-8', xml_declaration=True)

    def _convert_metadata_to_xml(self, metadata: GenericMetadata, xml: bytes = b'') -> ET.Element:
        # shorthand for the metadata
        md = metadata

        if xml:
            root = ET.fromstring(xml)
        else:
            # build a tree structure
            root = ET.Element('ComicInfo')
            root.attrib['xmlns:xsi'] = 'http://www.w3.org/2001/XMLSchema-instance'
            root.attrib['xmlns:xsd'] = 'http://www.w3.org/2001/XMLSchema'
        # helper func

        def assign(cr_entry: str, md_entry: Any) -> None:
            if md_entry:
                text = ''
                if isinstance(md_entry, str):
                    text = md_entry
                elif isinstance(md_entry, (list, set)):
                    text = ','.join(md_entry)
                else:
                    text = str(md_entry)
                et_entry = root.find(cr_entry)
                if et_entry is not None:
                    et_entry.text = text
                else:
                    ET.SubElement(root, cr_entry).text = text
            else:
                et_entry = root.find(cr_entry)
                if et_entry is not None:
                    root.remove(et_entry)

        # need to specially process the credits, since they are structured
        # differently than CIX
        credit_writer_list = []
        credit_penciller_list = []
        credit_inker_list = []
        credit_colorist_list = []
        credit_letterer_list = []
        credit_cover_list = []
        credit_editor_list = []
        credit_translator_list = []

        # first, loop thru credits, and build a list for each role that CIX
        # supports
        for credit in metadata.credits:
            if credit['role'].casefold() in GenericMetadata.writer_synonyms:
                credit_writer_list.append(credit['person'].replace(',', ''))

            if credit['role'].casefold() in GenericMetadata.penciller_synonyms:
                credit_penciller_list.append(credit['person'].replace(',', ''))

            if credit['role'].casefold() in GenericMetadata.inker_synonyms:
                credit_inker_list.append(credit['person'].replace(',', ''))

            if credit['role'].casefold() in GenericMetadata.colorist_synonyms:
                credit_colorist_list.append(credit['person'].replace(',', ''))

            if credit['role'].casefold() in GenericMetadata.letterer_synonyms:
                credit_letterer_list.append(credit['person'].replace(',', ''))

            if credit['role'].casefold() in GenericMetadata.cover_synonyms:
                credit_cover_list.append(credit['person'].replace(',', ''))

            if credit['role'].casefold() in GenericMetadata.editor_synonyms:
                credit_editor_list.append(credit['person'].replace(',', ''))

            if credit['role'].casefold() in GenericMetadata.translator_synonyms:
                credit_translator_list.append(credit['person'].replace(',', ''))

        assign('Series', md.series)
        assign('Number', md.issue)
        assign('Count', md.issue_count)
        assign('Title', md.title)
        assign('Volume', md.volume)
        assign('Genre', md.genres)
        assign('Summary', md.description)
        assign('Notes', md.notes)

        assign('AlternateSeries', md.alternate_series)
        assign('AlternateNumber', md.alternate_number)
        assign('AlternateCount', md.alternate_count)
        assign('StoryArc', md.story_arcs)
        assign('SeriesGroup', md.series_groups)

        assign('Publisher', md.publisher)
        assign('Imprint', md.imprint)
        assign('Day', md.day)
        assign('Month', md.month)
        assign('Year', md.year)
        assign('LanguageISO', md.language)
        assign('Web', md.web_link)
        assign('Format', md.format)
        assign('Manga', md.manga)
        assign('BlackAndWhite', 'Yes' if md.black_and_white else None)
        assign('AgeRating', md.maturity_rating)
        assign('CommunityRating', md.critical_rating)
        assign('ScanInformation', md.scan_info)

        assign('Tags', md.tags)
        assign('PageCount', md.page_count)

        assign('Characters', md.characters)
        assign('Teams', md.teams)
        assign('Locations', md.locations)
        assign('Writer', credit_writer_list)
        assign('Penciller', credit_penciller_list)
        assign('Inker', credit_inker_list)
        assign('Colorist', credit_colorist_list)
        assign('Letterer', credit_letterer_list)
        assign('CoverArtist', credit_cover_list)
        assign('Editor', credit_editor_list)
        assign('Translator', credit_translator_list)

        #  loop and add the page entries under pages node
        pages_node = root.find('Pages')
        if pages_node is not None:
            pages_node.clear()
        else:
            pages_node = ET.SubElement(root, 'Pages')

        for page_dict in md.pages:
            page_node = ET.SubElement(pages_node, 'Page')
            page_node.attrib = {}
            if 'bookmark' in page_dict:
                page_node.attrib['Bookmark'] = str(page_dict['bookmark'])
            if 'double_page' in page_dict:
                page_node.attrib['DoublePage'] = str(page_dict['double_page'])
            if 'image_index' in page_dict:
                page_node.attrib['Image'] = str(page_dict['image_index'])
            if 'height' in page_dict:
                page_node.attrib['ImageHeight'] = str(page_dict['height'])
            if 'size' in page_dict:
                page_node.attrib['ImageSize'] = str(page_dict['size'])
            if 'width' in page_dict:
                page_node.attrib['ImageWidth'] = str(page_dict['width'])
            if 'type' in page_dict:
                page_node.attrib['Type'] = str(page_dict['type'])
            page_node.attrib = OrderedDict(sorted(page_node.attrib.items()))

        ET.indent(root)

        return root

    def _convert_xml_to_metadata(self, root: ET.Element) -> GenericMetadata:
        if root.tag != 'ComicInfo':
            raise Exception('Not a ComicInfo file')

        def get(name: str) -> str | None:
            tag = root.find(name)
            if tag is None:
                return None
            return tag.text

        md = GenericMetadata()

        md.series = utils.xlate(get('Series'))
        md.issue = utils.xlate(get('Number'))
        md.issue_count = utils.xlate_int(get('Count'))
        md.title = utils.xlate(get('Title'))
        md.volume = utils.xlate_int(get('Volume'))
        md.genres = set(utils.split(get('Genre'), ','))
        md.description = utils.xlate(get('Summary'))
        md.notes = utils.xlate(get('Notes'))

        md.alternate_series = utils.xlate(get('AlternateSeries'))
        md.alternate_number = utils.xlate(get('AlternateNumber'))
        md.alternate_count = utils.xlate_int(get('AlternateCount'))
        md.story_arcs = utils.split(get('StoryArc'), ',')
        md.series_groups = utils.split(get('SeriesGroup'), ',')

        md.publisher = utils.xlate(get('Publisher'))
        md.imprint = utils.xlate(get('Imprint'))
        md.day = utils.xlate_int(get('Day'))
        md.month = utils.xlate_int(get('Month'))
        md.year = utils.xlate_int(get('Year'))
        md.language = utils.xlate(get('LanguageISO'))
        md.web_link = utils.xlate(get('Web'))
        md.format = utils.xlate(get('Format'))
        md.manga = utils.xlate(get('Manga'))
        md.maturity_rating = utils.xlate(get('AgeRating'))
        md.critical_rating = utils.xlate_float(get('CommunityRating'))
        md.scan_info = utils.xlate(get('ScanInformation'))

        md.tags = set(utils.split(get('Tags'), ','))
        md.page_count = utils.xlate_int(get('PageCount'))

        md.characters = set(utils.split(get('Characters'), ','))
        md.teams = set(utils.split(get('Teams'), ','))
        md.locations = set(utils.split(get('Locations'), ','))

        tmp = utils.xlate(get('BlackAndWhite'))
        if tmp is not None:
            md.black_and_white = tmp.casefold() in {'yes', 'true', '1'}

        # Now extract the credit info
        for n in root:
            if n.tag in {'Writer', 'Penciller', 'Inker', 'Colorist', 'Letterer', 'Editor'} and n.text is not None:
                for name in utils.split(n.text, ','):
                    md.add_credit(name.strip(), n.tag)

            if n.tag == 'CoverArtist' and n.text is not None:
                for name in utils.split(n.text, ','):
                    md.add_credit(name.strip(), 'Cover')

        # parse page data now
        pages_node = root.find('Pages')
        if pages_node is not None:
            for i, page in enumerate(pages_node):
                p: dict[str, Any] = page.attrib
                md_page = ImageMetadata(image_index=int(p.get('Image', i)))

                if 'Bookmark' in p:
                    md_page['bookmark'] = p['Bookmark']
                if 'DoublePage' in p:
                    md_page['double_page'] = p['DoublePage'].casefold() in ('yes', 'true', '1')
                if 'ImageHeight' in p:
                    md_page['height'] = p['ImageHeight']
                if 'ImageSize' in p:
                    md_page['size'] = p['ImageSize']
                if 'ImageWidth' in p:
                    md_page['width'] = p['ImageWidth']
                if 'Type' in p:
                    md_page['type'] = p['Type']

                md.pages.append(md_page)

        md.is_empty = False

        return md

    def _validate_bytes(self, string: bytes) -> bool:
        """Verify that the string actually contains CIX data in XML format."""
        try:
            root = ET.fromstring(string)
            if root.tag != 'ComicInfo':
                return False
        except ET.ParseError:
            return False

        return True
