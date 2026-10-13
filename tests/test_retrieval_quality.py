"""
Test suite for retrieval quality debugging.

Tests the 3-part fix:
1. CHUNKING: Structure-aware splitting for enumerated lists
2. RETRIEVAL: Debug logging for BM25+FAISS hybrid scoring
3. SYNTHESIS: Completeness check for count-specified queries
"""

import json
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Any

import pytest

# Configure logging to see debug output
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# ============================================================================
# Test Document: "4 Types of AI"
# ============================================================================

TEST_DOCUMENT_CONTENT = """
ARTIFICIAL INTELLIGENCE TYPES AND CLASSIFICATIONS

Introduction
Artificial Intelligence (AI) has evolved significantly over the past decades. 
Understanding the different types of AI is crucial for researchers and practitioners.

SECTION 1: FOUR MAIN TYPES OF AI

The field of AI can be categorized into four distinct types based on their capabilities 
and level of autonomy:

1. Reactive AI
   Reactive AI systems are the most basic form of artificial intelligence. These systems 
   do not have memory and operate based on current inputs. They process information and 
   respond immediately without learning from past experiences. Examples include chess-playing 
   computers like Deep Blue, which evaluate the current board state and make optimal moves 
   without remembering previous games. Reactive AI is deterministic and follows pre-programmed 
   rules to generate outputs from inputs.

2. Limited Memory AI
   Limited Memory AI systems use historical data to make decisions. These systems retain 
   information from past interactions and use this data to improve their decision-making 
   processes. Most current AI applications, including machine learning models and deep 
   learning systems, fall into this category. Limited Memory AI can learn from training 
   data and adapt its behavior based on new information. This type includes recommendation 
   systems, chatbots, and autonomous vehicles that learn from sensor data over time.

3. Theory-of-Mind AI
   Theory-of-Mind AI represents a more advanced form of artificial intelligence that aims 
   to understand human emotions, beliefs, intentions, and desires. This type of AI would be 
   able to comprehend social intelligence, emotional intelligence, and theory of mind concepts. 
   Theory-of-Mind AI is still largely in the research phase and has not been fully realized 
   in practical applications. It would require understanding context, nuance, and the 
   psychological aspects of human interaction.

4. Self-Aware AI
   Self-Aware AI, also known as Artificial General Intelligence (AGI) or Super Intelligence, 
   represents the most advanced and theoretical form of AI. This type of AI would possess 
   consciousness and self-awareness, understanding its own existence and capabilities. 
   Self-Aware AI remains purely theoretical and has not been achieved yet. It would represent 
   a level of intelligence equal to or exceeding human intelligence across all domains.

SECTION 2: HEALTHCARE APPLICATIONS

Healthcare is one of the most promising domains for AI applications. Hospitals and clinics 
are increasingly adopting AI-powered diagnostic systems. These systems can analyze medical 
imaging, predict patient outcomes, and assist in treatment planning. The integration of AI 
in healthcare has shown significant improvements in patient care and operational efficiency.

SECTION 3: COMPARISON WITH OTHER FRAMEWORKS

While the four-type framework is widely accepted, some researchers propose alternative 
categorizations. However, the Reactive, Limited Memory, Theory-of-Mind, and Self-Aware 
classification remains the most comprehensive and widely used framework in academic literature.

Conclusion
Understanding these four types of AI is essential for anyone working in the field. Each type 
represents a different level of sophistication and capability. As AI continues to evolve, 
we may see the emergence of Theory-of-Mind and Self-Aware AI systems in the coming decades.
"""


# ============================================================================
# PART 1: CHUNKING TESTS
# ============================================================================

class TestChunkingStructureAwareness:
    """Test that enumerated lists stay together in chunks."""

    def test_enumerated_list_stays_intact(self):
        """Verify that all 4 AI types stay in a single chunk."""
        from core.document_processor import DocumentProcessor
        from config.settings import SystemConfig
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(TEST_DOCUMENT_CONTENT)
            temp_path = f.name
        
        try:
            processor = DocumentProcessor(google_api_key="test-key")
            result = processor.process_document(temp_path, file_type='.txt')
            
            assert result['success'], f"Processing failed: {result.get('error')}"
            
            reactive_chunk = None
            for doc in processor.documents:
                if "Reactive AI" in doc.page_content:
                    reactive_chunk = doc
                    break
            
            assert reactive_chunk is not None, "Reactive AI chunk not found"
            
            content = reactive_chunk.page_content
            assert "Reactive AI" in content, "Reactive AI not in chunk"
            assert "Limited Memory AI" in content, "Limited Memory AI not in chunk"
            assert "Theory-of-Mind AI" in content, "Theory-of-Mind AI not in chunk"
            assert "Self-Aware AI" in content, "Self-Aware AI not in chunk"
            
            assert "do not have memory" in content, "Reactive AI definition missing"
            assert "historical data" in content, "Limited Memory AI definition missing"
            assert "emotions, beliefs, intentions" in content, "Theory-of-Mind definition missing"
            assert "consciousness and self-awareness" in content, "Self-Aware AI definition missing"
            
            logger.info(f"✓ All 4 AI types found in single chunk ({len(content)} chars)")
            
        finally:
            Path(temp_path).unlink()

    def test_chunk_boundaries_before_fix(self):
        """Log chunk boundaries BEFORE the fix (for comparison)."""
        from core.document_processor import DocumentProcessor
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(TEST_DOCUMENT_CONTENT)
            temp_path = f.name
        
        try:
            processor = DocumentProcessor(google_api_key="test-key")
            result = processor.process_document(temp_path, file_type='.txt')
            
            logger.info("\n" + "="*70)
            logger.info("CHUNK BOUNDARIES (BEFORE FIX)")
            logger.info("="*70)
            
            for i, doc in enumerate(processor.documents):
                content = doc.page_content
                lines = [l.strip() for l in content.split('\n') if l.strip()]
                first_line = lines[0][:60] if lines else "N/A"
                last_line = lines[-1][:60] if lines else "N/A"
                
                logger.info(f"\nChunk {i}: {len(content)} chars")
                logger.info(f"  Start: {first_line}...")
                logger.info(f"  End:   ...{last_line}")
                
                ai_types = []
                if "Reactive AI" in content:
                    ai_types.append("Reactive")
                if "Limited Memory AI" in content:
                    ai_types.append("Limited Memory")
                if "Theory-of-Mind AI" in content:
                    ai_types.append("Theory-of-Mind")
                if "Self-Aware AI" in content:
                    ai_types.append("Self-Aware")
                
                if ai_types:
                    logger.info(f"  Contains: {', '.join(ai_types)}")
            
            logger.info("\n" + "="*70)
            
        finally:
            Path(temp_path).unlink()


# ============================================================================
# PART 2: RETRIEVAL TESTS
# ============================================================================

class TestRetrievalDebugLogging:
    """Test hybrid BM25+FAISS retrieval with detailed scoring logs."""

    def test_retrieval_scoring_for_ai_types_query(self):
        """Log BM25, FAISS, and RRF scores for 'what are 4 types of AI' query."""
        from core.document_processor import DocumentProcessor
        from agents.literature_scanner import rerank_chunks
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(TEST_DOCUMENT_CONTENT)
            temp_path = f.name
        
        try:
            processor = DocumentProcessor(google_api_key="test-key")
            result = processor.process_document(temp_path, file_type='.txt')
            assert result['success']
            
            query = "what are 4 types of AI"
            
            faiss_results = processor.search_documents(query, k=10)
            bm25_results = processor.search_bm25(query, k=10)
            
            logger.info("\n" + "="*70)
            logger.info("RETRIEVAL SCORING DEBUG LOG")
            logger.info("="*70)
            logger.info(f"Query: '{query}'")
            logger.info(f"FAISS results: {len(faiss_results)}, BM25 results: {len(bm25_results)}")
            
            logger.info("\nFAISS SCORES (Vector Similarity):")
            for i, chunk in enumerate(faiss_results[:5], 1):
                content_preview = chunk['content'][:60].replace('\n', ' ')
                logger.info(
                    f"  {i}. Similarity={chunk['similarity_score']:.4f} | "
                    f"{content_preview}..."
                )
            
            logger.info("\nBM25 SCORES (Keyword Overlap):")
            for i, chunk in enumerate(bm25_results[:5], 1):
                content_preview = chunk['content'][:60].replace('\n', ' ')
                logger.info(
                    f"  {i}. BM25={chunk['bm25_score']:.4f} | "
                    f"{content_preview}..."
                )
            
            reranked = rerank_chunks(query, faiss_results, top_n=10)
            
            logger.info("\nCOMBINED SCORES (0.7*FAISS + 0.3*Keyword):")
            for i, chunk in enumerate(reranked[:5], 1):
                content_preview = chunk['content'][:60].replace('\n', ' ')
                logger.info(
                    f"  {i}. Combined={chunk['combined_score']:.4f} "
                    f"(sim={chunk['similarity_score']:.4f}, kw={chunk['keyword_overlap']:.4f}) | "
                    f"{content_preview}..."
                )
            
            four_types_found = False
            for i, chunk in enumerate(reranked[:5], 1):
                if all(t in chunk['content'] for t in ["Reactive AI", "Limited Memory AI", 
                                                         "Theory-of-Mind AI", "Self-Aware AI"]):
                    logger.info(f"\n✓ All 4 AI types found in rank {i}")
                    four_types_found = True
                    break
            
            if not four_types_found:
                logger.warning("\n✗ All 4 AI types NOT in top 5 results")
            
            logger.info("\n" + "="*70)
            
            assert four_types_found, "4 AI types chunk should be in top results"
            
        finally:
            Path(temp_path).unlink()

    def test_healthcare_chunk_ranking(self):
        """Verify that irrelevant 'Healthcare' chunk doesn't outrank the 4-types chunk."""
        from core.document_processor import DocumentProcessor
        from agents.literature_scanner import rerank_chunks
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(TEST_DOCUMENT_CONTENT)
            temp_path = f.name
        
        try:
            processor = DocumentProcessor(google_api_key="test-key")
            result = processor.process_document(temp_path, file_type='.txt')
            assert result['success']
            
            query = "what are 4 types of AI"
            faiss_results = processor.search_documents(query, k=10)
            reranked = rerank_chunks(query, faiss_results, top_n=10)
            
            four_types_rank = None
            healthcare_rank = None
            
            for i, chunk in enumerate(reranked, 1):
                if all(t in chunk['content'] for t in ["Reactive AI", "Limited Memory AI"]):
                    four_types_rank = i
                if "Healthcare" in chunk['content'] and "diagnostic" in chunk['content']:
                    healthcare_rank = i
            
            logger.info(f"\n4-types chunk rank: {four_types_rank}")
            logger.info(f"Healthcare chunk rank: {healthcare_rank}")
            
            if four_types_rank and healthcare_rank:
                assert four_types_rank < healthcare_rank, \
                    f"4-types (rank {four_types_rank}) should outrank healthcare (rank {healthcare_rank})"
            
        finally:
            Path(temp_path).unlink()


# ============================================================================
# PART 3: SYNTHESIS COMPLETENESS TESTS
# ============================================================================

class TestSynthesisCompletenessCheck:
    """Test that synthesis detects and reports incomplete answers for count-specified queries."""

    def test_completeness_check_for_count_query(self):
        """Verify synthesis checks for 'X items' when query specifies a count."""
        from core.models import ResearchSynthesis
        
        partial_synthesis = ResearchSynthesis(
            research_question="what are 4 types of AI",
            key_findings=[
                "Reactive AI systems do not have memory [Paper 1]",
                "Limited Memory AI uses historical data [Paper 1]",
            ],
            methodology_insights=[
                "The document categorizes AI by capabilities [Paper 1]",
            ],
            research_gaps=[
                "The document may not fully cover all aspects",
            ],
            recommended_papers=["Test Document"],
            confidence_score=0.6,
            technical_contributions=[],
            comparative_analysis=[],
            practical_implications=[],
        )
        
        question = partial_synthesis.research_question.lower()
        
        import re
        count_match = re.search(r'(\d+)\s+(?:types|kinds|categories|reasons|steps|ways)', question)
        
        if count_match:
            expected_count = int(count_match.group(1))
            actual_count = len(partial_synthesis.key_findings)
            
            logger.info(f"\nCompleteness Check:")
            logger.info(f"  Question: '{partial_synthesis.research_question}'")
            logger.info(f"  Expected items: {expected_count}")
            logger.info(f"  Found items: {actual_count}")
            
            if actual_count < expected_count:
                logger.warning(
                    f"  ⚠️ INCOMPLETE: Found {actual_count} of {expected_count} items"
                )
                assert False, f"Synthesis incomplete: found {actual_count} of {expected_count} items"
            else:
                logger.info(f"  ✓ Complete: Found all {expected_count} items")

    def test_completeness_check_integration(self):
        """Test completeness check in full synthesis pipeline."""
        from core.document_processor import DocumentProcessor
        from agents.literature_scanner import LiteratureScanner, determine_k
        from core.models import ResearchDomain
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(TEST_DOCUMENT_CONTENT)
            temp_path = f.name
        
        try:
            processor = DocumentProcessor(google_api_key="test-key")
            result = processor.process_document(temp_path, file_type='.txt')
            assert result['success']
            
            query = "what are 4 types of AI"
            
            k = determine_k(query)
            logger.info(f"\nQuery: '{query}'")
            logger.info(f"Dynamic k: {k}")
            
            raw_chunks = processor.search_documents(query, k=k)
            
            all_types_found = all(
                any(t in chunk['content'] for chunk in raw_chunks)
                for t in ["Reactive AI", "Limited Memory AI", "Theory-of-Mind AI", "Self-Aware AI"]
            )
            
            logger.info(f"All 4 types found in retrieval: {all_types_found}")
            assert all_types_found, "All 4 AI types should be retrievable"
            
        finally:
            Path(temp_path).unlink()


# ============================================================================
# INTEGRATION TEST
# ============================================================================

class TestFullPipelineWithFixes:
    """End-to-end test of the complete retrieval + synthesis pipeline."""

    def test_full_pipeline_returns_all_4_types(self):
        """Verify the complete pipeline returns all 4 AI types with definitions."""
        from core.document_processor import DocumentProcessor
        from agents.literature_scanner import LiteratureScanner, determine_k, rerank_chunks
        from core.models import ResearchDomain
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(TEST_DOCUMENT_CONTENT)
            temp_path = f.name
        
        try:
            processor = DocumentProcessor(google_api_key="test-key")
            result = processor.process_document(temp_path, file_type='.txt')
            assert result['success']
            
            query = "what are 4 types of AI"
            k = determine_k(query)
            
            raw_chunks = processor.search_documents(query, k=k)
            reranked = rerank_chunks(query, raw_chunks, top_n=k)
            
            combined_content = "\n".join(chunk['content'] for chunk in reranked[:3])
            
            logger.info("\n" + "="*70)
            logger.info("FULL PIPELINE TEST RESULTS")
            logger.info("="*70)
            logger.info(f"Query: '{query}'")
            logger.info(f"Dynamic k: {k}")
            logger.info(f"Top {k} chunks combined: {len(combined_content)} chars")
            
            types_found = {
                "Reactive AI": "Reactive AI" in combined_content,
                "Limited Memory AI": "Limited Memory AI" in combined_content,
                "Theory-of-Mind AI": "Theory-of-Mind AI" in combined_content,
                "Self-Aware AI": "Self-Aware AI" in combined_content,
            }
            
            for type_name, found in types_found.items():
                status = "✓" if found else "✗"
                logger.info(f"  {status} {type_name}")
            
            definitions_found = {
                "Reactive (no memory)": "do not have memory" in combined_content,
                "Limited Memory (historical)": "historical data" in combined_content,
                "Theory-of-Mind (emotions)": "emotions, beliefs, intentions" in combined_content,
                "Self-Aware (consciousness)": "consciousness and self-awareness" in combined_content,
            }
            
            logger.info("\nDefinitions found:")
            for def_name, found in definitions_found.items():
                status = "✓" if found else "✗"
                logger.info(f"  {status} {def_name}")
            
            logger.info("="*70)
            
            assert all(types_found.values()), f"Not all AI types found: {types_found}"
            assert all(definitions_found.values()), f"Not all definitions found: {definitions_found}"
            
        finally:
            Path(temp_path).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
