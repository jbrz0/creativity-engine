"""Pinecone vector database client."""

from typing import List, Dict, Any, Optional
import structlog
from pinecone import Pinecone, ServerlessSpec
import hashlib

from src.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class PineconeClient:
    """Client for interacting with Pinecone vector database."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        environment: Optional[str] = None,
        index_name: Optional[str] = None,
    ):
        """Initialize Pinecone client.

        Args:
            api_key: Pinecone API key
            environment: Pinecone environment
            index_name: Index name to use
        """
        self.api_key = api_key or settings.pinecone_api_key
        self.environment = environment or settings.pinecone_environment
        self.index_name = index_name or settings.pinecone_index_name

        # Initialize Pinecone
        self.pc = Pinecone(api_key=self.api_key)
        self.index = None

        logger.info(
            "Initializing Pinecone client",
            environment=self.environment,
            index_name=self.index_name,
        )

    async def initialize(self, dimension: int = 1536) -> None:
        """Initialize or connect to Pinecone index.

        Args:
            dimension: Vector dimension (default 1536 for OpenAI embeddings)
        """
        try:
            # Check if index exists
            existing_indexes = self.pc.list_indexes()
            index_names = [idx.name for idx in existing_indexes]

            if self.index_name not in index_names:
                logger.info("Creating Pinecone index", index_name=self.index_name, dimension=dimension)

                # Create index with serverless spec
                self.pc.create_index(
                    name=self.index_name,
                    dimension=dimension,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1"),  # Free tier supports us-east-1
                )

                logger.info("Pinecone index created successfully")
            else:
                logger.info("Pinecone index already exists", index_name=self.index_name)

            # Connect to index
            self.index = self.pc.Index(self.index_name)
            logger.info("Connected to Pinecone index")

        except Exception as e:
            logger.error("Failed to initialize Pinecone", error=str(e))
            raise

    async def upsert_vectors(
        self,
        vectors: List[Dict[str, Any]],
        namespace: str = "",
    ) -> Dict[str, int]:
        """Upsert vectors to Pinecone.

        Args:
            vectors: List of vector dictionaries with 'id', 'values', and optionally 'metadata'
            namespace: Optional namespace for organizing vectors

        Returns:
            Upsert statistics
        """
        if not self.index:
            raise RuntimeError("Pinecone index not initialized. Call initialize() first.")

        try:
            response = self.index.upsert(vectors=vectors, namespace=namespace)
            logger.debug(
                "Upserted vectors to Pinecone",
                count=len(vectors),
                namespace=namespace,
                upserted_count=response.get("upserted_count", 0),
            )
            return response
        except Exception as e:
            logger.error("Failed to upsert vectors", error=str(e))
            raise

    async def query_vectors(
        self,
        vector: List[float],
        top_k: int = 10,
        namespace: str = "",
        filter_dict: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
    ) -> List[Dict[str, Any]]:
        """Query similar vectors from Pinecone.

        Args:
            vector: Query vector
            top_k: Number of results to return
            namespace: Optional namespace
            filter_dict: Optional metadata filter
            include_metadata: Whether to include metadata in results

        Returns:
            List of matching vectors with scores
        """
        if not self.index:
            raise RuntimeError("Pinecone index not initialized. Call initialize() first.")

        try:
            response = self.index.query(
                vector=vector,
                top_k=top_k,
                namespace=namespace,
                filter=filter_dict,
                include_metadata=include_metadata,
                include_values=False,
            )

            results = []
            for match in response.get("matches", []):
                results.append(
                    {
                        "id": match.get("id"),
                        "score": match.get("score"),
                        "metadata": match.get("metadata", {}),
                    }
                )

            logger.debug(
                "Queried Pinecone",
                top_k=top_k,
                namespace=namespace,
                results_count=len(results),
            )

            return results

        except Exception as e:
            logger.error("Failed to query vectors", error=str(e))
            raise

    async def delete_vectors(
        self,
        ids: List[str],
        namespace: str = "",
    ) -> None:
        """Delete vectors from Pinecone.

        Args:
            ids: List of vector IDs to delete
            namespace: Optional namespace
        """
        if not self.index:
            raise RuntimeError("Pinecone index not initialized. Call initialize() first.")

        try:
            self.index.delete(ids=ids, namespace=namespace)
            logger.debug("Deleted vectors from Pinecone", count=len(ids), namespace=namespace)
        except Exception as e:
            logger.error("Failed to delete vectors", error=str(e))
            raise

    async def fetch_vectors(
        self,
        ids: List[str],
        namespace: str = "",
    ) -> Dict[str, Any]:
        """Fetch specific vectors by ID.

        Args:
            ids: List of vector IDs to fetch
            namespace: Optional namespace

        Returns:
            Dictionary of vectors
        """
        if not self.index:
            raise RuntimeError("Pinecone index not initialized. Call initialize() first.")

        try:
            response = self.index.fetch(ids=ids, namespace=namespace)
            logger.debug("Fetched vectors from Pinecone", count=len(ids), namespace=namespace)
            return response.get("vectors", {})
        except Exception as e:
            logger.error("Failed to fetch vectors", error=str(e))
            raise

    @staticmethod
    def generate_id(text: str, prefix: str = "") -> str:
        """Generate a deterministic ID from text.

        Args:
            text: Text to hash
            prefix: Optional prefix for the ID

        Returns:
            Generated ID
        """
        hash_object = hashlib.sha256(text.encode())
        hash_hex = hash_object.hexdigest()[:16]
        return f"{prefix}{hash_hex}" if prefix else hash_hex


# Global client instance
_pinecone_client: Optional[PineconeClient] = None


async def get_pinecone_client() -> PineconeClient:
    """Get the global Pinecone client instance."""
    global _pinecone_client
    if _pinecone_client is None:
        _pinecone_client = PineconeClient()
        await _pinecone_client.initialize()
    return _pinecone_client


async def close_pinecone_client() -> None:
    """Close the global Pinecone client."""
    global _pinecone_client
    _pinecone_client = None
