package ncbi.taggerOne.util;

import static org.junit.Assert.*;

import java.util.Arrays;
import java.util.List;

import org.junit.Test;

public class TrieTest {

	@Test
	public void test() {

		Trie<String, String> trie = new Trie<String, String>();

		assertEquals(0, trie.size());

		trie.add(makeList("a", "b"), "v0");

		assertEquals(null, trie.get(makeList()));
		assertEquals(null, trie.get(makeList("a")));
		assertEquals("v0", trie.get(makeList("a", "b")));
		assertEquals(null, trie.get(makeList("a", "c")));
		assertEquals(null, trie.get(makeList("b")));
		assertEquals(null, trie.get(makeList("a", "b", "c")));
		assertEquals(1, trie.size());

		trie.add(makeList("a", "c"), "v1");

		assertEquals(null, trie.get(makeList("a")));
		assertEquals("v0", trie.get(makeList("a", "b")));
		assertEquals("v1", trie.get(makeList("a", "c")));
		assertEquals(null, trie.get(makeList("b")));
		assertEquals(null, trie.get(makeList("a", "b", "c")));
		assertEquals(2, trie.size());

		trie.add(makeList("a", "b", "c"), "v2");

		assertEquals(null, trie.get(makeList("a")));
		assertEquals("v0", trie.get(makeList("a", "b")));
		assertEquals("v1", trie.get(makeList("a", "c")));
		assertEquals(null, trie.get(makeList("b")));
		assertEquals("v2", trie.get(makeList("a", "b", "c")));
		assertEquals(3, trie.size());

		trie.add(makeList("a", "b"), "v3");

		assertEquals(null, trie.get(makeList("a")));
		assertEquals("v3", trie.get(makeList("a", "b")));
		assertEquals("v1", trie.get(makeList("a", "c")));
		assertEquals(null, trie.get(makeList("b")));
		assertEquals("v2", trie.get(makeList("a", "b", "c")));
		assertEquals(3, trie.size());

		trie.add(makeList("a", "b", "c", "d", "e"), "v4");

		assertEquals(null, trie.get(makeList("a")));
		assertEquals("v3", trie.get(makeList("a", "b")));
		assertEquals("v1", trie.get(makeList("a", "c")));
		assertEquals(null, trie.get(makeList("b")));
		assertEquals("v2", trie.get(makeList("a", "b", "c")));
		assertEquals("v4", trie.get(makeList("a", "b", "c", "d", "e")));
		assertEquals(4, trie.size());

	}

	private static List<String> makeList(String... strings) {
		return Arrays.asList(strings);
	}
}
