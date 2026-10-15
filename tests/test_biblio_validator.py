import unittest
from unittest.mock import MagicMock
from src.core.biblio_validator import (
    BiblioValidator,
    compute_string_similarity,
    clean_doi_string,
)


class TestBiblioValidator(unittest.TestCase):

    def test_string_similarity(self):
        self.assertEqual(compute_string_similarity("Attention Is All You Need", "Attention is all you need"), 1.0)
        self.assertGreater(compute_string_similarity("Deep Residual Learning for Image Recognition", "Deep Residual Learning"), 0.65)
        self.assertLess(compute_string_similarity("Completely Unrelated Subject", "Quantum Computing Algorithms"), 0.3)

    def test_clean_doi(self):
        self.assertEqual(clean_doi_string("https://doi.org/10.1038/nature12373"), "10.1038/nature12373")
        self.assertEqual(clean_doi_string("http://dx.doi.org/10.1109/TBME.2020.123456"), "10.1109/tbme.2020.123456")
        self.assertEqual(clean_doi_string("10.1016/j.neucom.2021.01.001"), "10.1016/j.neucom.2021.01.001")
        self.assertIsNone(clean_doi_string("not_a_doi"))

    def test_parse_bibtex(self):
        sample_bib = """
        @article{vaswani2017attention,
          title={Attention is all you need},
          author={Vaswani, Ashish and Shazeer, Noam and Parmar, Niki},
          journal={Advances in Neural Information Processing Systems},
          year={2017},
          doi={10.48550/arXiv.1706.03762}
        }

        @inproceedings{fake2024hallucinated,
          title={Fabricated Study on Quantum Teleportation in Brain Waves},
          author={Smith, John},
          year={2024},
          doi={10.99999/hallucinated.fake.doi}
        }
        """
        entries = BiblioValidator.parse_bibtex(sample_bib)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["cite_key"], "vaswani2017attention")
        self.assertEqual(entries[0]["title"], "Attention is all you need")
        self.assertEqual(entries[0]["doi"], "10.48550/arXiv.1706.03762")
        self.assertEqual(entries[0]["year"], 2017)

        self.assertEqual(entries[1]["cite_key"], "fake2024hallucinated")
        self.assertEqual(entries[1]["title"], "Fabricated Study on Quantum Teleportation in Brain Waves")

    def test_mock_hallucination_detection(self):
        validator = BiblioValidator()

        # Case 1: Authentic matching paper
        validator.query_crossref_doi = MagicMock(side_effect=lambda doi: {
            "ground_truth_title": "Attention Is All You Need",
            "ground_truth_authors": "Ashish Vaswani; Noam Shazeer",
            "ground_truth_year": 2017,
            "ground_truth_doi": doi,
            "source": "crossref"
        } if doi == "10.48550/arxiv.1706.03762" else None)

        res_valid = validator.verify_entry({
            "cite_key": "vaswani2017",
            "title": "Attention Is All You Need",
            "doi": "10.48550/arXiv.1706.03762",
            "year": 2017
        })
        self.assertEqual(res_valid["status"], "VERIFIED")
        self.assertFalse(res_valid["is_hallucination_suspect"])

        # Case 2: Hallucinated DOI mismatch (Real DOI attached to fake/different paper title)
        res_mismatch = validator.verify_entry({
            "cite_key": "fake_link",
            "title": "Noninvasive Brain Interfaces for Space Exploration",
            "doi": "10.48550/arXiv.1706.03762",
            "year": 2024
        })
        self.assertEqual(res_mismatch["status"], "HALLUCINATED_DOI_MISMATCH")
        self.assertTrue(res_mismatch["is_hallucination_suspect"])

        # Case 3: Completely non-existent DOI
        res_fake_doi = validator.verify_entry({
            "cite_key": "fake_doi",
            "title": "Quantum Brain Teleportation",
            "doi": "10.99999/fake.doi.123",
            "year": 2024
        })
        self.assertTrue(res_fake_doi["is_hallucination_suspect"])
        self.assertIn("HALLUCINATED", res_fake_doi["status"])

    def test_methodology_domain_check(self):
        validator = BiblioValidator()

        # Case 1: Barrington et al. (True bibliometric study)
        is_match, reason, cues = validator.check_study_methodology(
            title="A Bibliometric Analysis of the Rise of ChatGPT in Medical Research",
            abstract="We performed a scientometric evaluation using VOSviewer and Web of Science.",
            topics=["scientometrics and bibliometrics research", "Academic Writing"],
            expected_domain="bibliometric"
        )
        self.assertTrue(is_match)
        self.assertIn("text:bibliometric", cues)

        # Case 2: Kung et al. (Exam performance paper without bibliometrics)
        is_match_kung, reason_kung, cues_kung = validator.check_study_methodology(
            title="Performance of ChatGPT on USMLE: Potential for AI-Assisted Medical Education",
            abstract="We evaluated the performance of ChatGPT on the United States Medical Licensing Examination.",
            topics=["Innovations in Medical Education", "Artificial Intelligence in Education"],
            concepts=["Concordance", "United States Medical Licensing Examination"],
            expected_domain="bibliometric"
        )
        self.assertFalse(is_match_kung)
        self.assertEqual(len(cues_kung), 0)
        self.assertIn("No bibliometric keywords found", reason_kung)

    def test_domain_filtering_in_verify_entry(self):
        validator = BiblioValidator()

        # Mock query_doi returning Kung et al metadata
        validator.query_doi = MagicMock(return_value={
            "ground_truth_title": "Performance of ChatGPT on USMLE: Potential for AI-Assisted Medical Education",
            "ground_truth_authors": "Tiffany H. Kung; Victor Tseng",
            "ground_truth_year": 2023,
            "ground_truth_doi": "10.1371/journal.pdig.0000198",
            "ground_truth_abstract": "We evaluated the performance of ChatGPT on the USMLE exam.",
            "ground_truth_topics": ["Innovations in Medical Education"],
            "ground_truth_concepts": ["Medical education"],
            "ground_truth_subjects": ["Digital Health"],
            "source": "crossref+openalex"
        })

        # When expected_domain is NOT set, citation is authentic
        res_standard = validator.verify_entry({
            "title": "Performance of ChatGPT on USMLE: Potential for AI-Assisted Medical Education",
            "doi": "10.1371/journal.pdig.0000198"
        })
        self.assertEqual(res_standard["status"], "VERIFIED")

        # When expected_domain is 'bibliometric', flag methodology mismatch!
        res_domain = validator.verify_entry({
            "title": "Performance of ChatGPT on USMLE: Potential for AI-Assisted Medical Education",
            "doi": "10.1371/journal.pdig.0000198"
        }, expected_domain="bibliometric")
        self.assertEqual(res_domain["status"], "FLAGGED_NON_BIBLIOMETRIC_STUDY")
        self.assertTrue(res_domain["is_domain_mismatch"])
        self.assertFalse(res_domain["domain_verified"])


if __name__ == "__main__":
    unittest.main()

