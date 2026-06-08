package ncbi.taggerOne.util;

import static org.junit.Assert.*;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;

import org.junit.Assert;
import org.junit.Test;

public class LRUCacheTest {

	@Test
	public void test1() {

		LRUCache<String, String> cache = new LRUCache<String, String>(LRUCache.DEFAULT_CAPACITY, LRUCache.DEFAULT_LOAD_FACTOR, 3);

		assertEquals(3, cache.getMaxSize());
		assertEquals(0, cache.size());
		assertEquals(null, cache.get("k0"));
		assertEquals(null, cache.get("k1"));
		assertEquals(null, cache.get("k2"));
		assertEquals(null, cache.get("k3"));

		cache.put("k0", "v0");

		assertEquals(3, cache.getMaxSize());
		assertEquals(1, cache.size());
		assertEquals("v0", cache.get("k0"));
		assertEquals(null, cache.get("k1"));
		assertEquals(null, cache.get("k2"));
		assertEquals(null, cache.get("k3"));

		cache.put("k1", "v1");

		assertEquals(3, cache.getMaxSize());
		assertEquals(2, cache.size());
		assertEquals("v0", cache.get("k0"));
		assertEquals("v1", cache.get("k1"));
		assertEquals(null, cache.get("k2"));
		assertEquals(null, cache.get("k3"));

		cache.put("k2", "v2");

		assertEquals(3, cache.getMaxSize());
		assertEquals(3, cache.size());
		assertEquals("v0", cache.get("k0"));
		assertEquals("v1", cache.get("k1"));
		assertEquals("v2", cache.get("k2"));
		assertEquals(null, cache.get("k3"));

		cache.put("k1", "v1");

		assertEquals(3, cache.getMaxSize());
		assertEquals(3, cache.size());
		assertEquals("v0", cache.get("k0"));
		assertEquals("v1", cache.get("k1"));
		assertEquals("v2", cache.get("k2"));
		assertEquals(null, cache.get("k3"));

		cache.put("k2", "v2b");

		assertEquals(3, cache.getMaxSize());
		assertEquals(3, cache.size());
		assertEquals("v0", cache.get("k0"));
		assertEquals("v1", cache.get("k1"));
		assertEquals("v2b", cache.get("k2"));
		assertEquals(null, cache.get("k3"));

		cache.put("k3", "v3");

		assertEquals(3, cache.getMaxSize());
		assertEquals(3, cache.size());
		assertEquals(null, cache.get("k0"));
		assertEquals("v1", cache.get("k1"));
		assertEquals("v2b", cache.get("k2"));
		assertEquals("v3", cache.get("k3"));

		cache.remove("k1");

		assertEquals(3, cache.getMaxSize());
		assertEquals(2, cache.size());
		assertEquals(null, cache.get("k0"));
		assertEquals(null, cache.get("k1"));
		assertEquals("v2b", cache.get("k2"));
		assertEquals("v3", cache.get("k3"));

		cache.put("k4", "v4");

		assertEquals(3, cache.getMaxSize());
		assertEquals(3, cache.size());
		assertEquals(null, cache.get("k0"));
		assertEquals(null, cache.get("k1"));
		assertEquals("v2b", cache.get("k2"));
		assertEquals("v3", cache.get("k3"));
		assertEquals("v4", cache.get("k4"));

		cache.put("k5", "v5");

		assertEquals(3, cache.getMaxSize());
		assertEquals(3, cache.size());
		assertEquals(null, cache.get("k0"));
		assertEquals(null, cache.get("k1"));
		assertEquals(null, cache.get("k2"));
		assertEquals("v3", cache.get("k3"));
		assertEquals("v4", cache.get("k4"));
		assertEquals("v5", cache.get("k5"));

		cache.clear();

		assertEquals(3, cache.getMaxSize());
		assertEquals(0, cache.size());
		assertEquals(null, cache.get("k0"));
		assertEquals(null, cache.get("k1"));
		assertEquals(null, cache.get("k2"));
		assertEquals(null, cache.get("k3"));
	}

	@Test
	public void testExceptions() {
		LRUCache<String, String> cache = null;
		try {
			cache = new LRUCache<String, String>(0, LRUCache.DEFAULT_LOAD_FACTOR, 3);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		try {
			cache = new LRUCache<String, String>(LRUCache.DEFAULT_CAPACITY, 0.0f, 3);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		try {
			cache = new LRUCache<String, String>(LRUCache.DEFAULT_CAPACITY, LRUCache.DEFAULT_LOAD_FACTOR, 0);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		cache = new LRUCache<String, String>(LRUCache.DEFAULT_CAPACITY, LRUCache.DEFAULT_LOAD_FACTOR, 3);
		try {
			cache.put(null, "v");
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		try {
			cache.put("k", null);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
	}

	@Test
	@SuppressWarnings("unchecked")
	public void testSerialization() {
		LRUCache<String, String> cache = new LRUCache<String, String>(LRUCache.DEFAULT_CAPACITY, LRUCache.DEFAULT_LOAD_FACTOR, 3);

		cache.put("k0", "v0");
		assertEquals(1, cache.size());
		assertEquals("v0", cache.get("k0"));

		LRUCache<String, String> copy = null;
		try {
			ByteArrayOutputStream sink = new ByteArrayOutputStream();
			ObjectOutputStream oos = new ObjectOutputStream(sink);
			oos.writeObject(cache);
			byte[] data = sink.toByteArray();
			oos.close();
			ObjectInputStream ois = new ObjectInputStream(new ByteArrayInputStream(data));
			copy = (LRUCache<String, String>) ois.readObject();
			ois.close();
		} catch (Exception e) {
			Assert.fail("Caught exception: " + e);
		}

		// Cache is cleared on serialization
		assertEquals(3, copy.getMaxSize());
		assertEquals(0, copy.size());
		assertEquals(null, copy.get("k0"));

		copy.put("k0", "v0");

		assertEquals(3, copy.getMaxSize());
		assertEquals(1, copy.size());
		assertEquals("v0", copy.get("k0"));
	}
}
