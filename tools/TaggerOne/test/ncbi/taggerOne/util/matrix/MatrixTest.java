package ncbi.taggerOne.util.matrix;

import static org.junit.Assert.*;

import java.util.HashSet;
import java.util.Set;

import ncbi.taggerOne.T1Constants;
import ncbi.taggerOne.util.Dictionary;

import org.junit.Assert;
import org.junit.Test;

public class MatrixTest {

	@Test
	public void testDense() {
		MatrixFactory factory = DenseMatrix.factory;
		testBasic(factory);
		testIncrement1(factory, DenseMatrix.factory);
		testIncrement2(factory, DenseMatrix.factory);
		testIncrement3(factory, DenseMatrix.factory);
		testIncrement4(factory, DenseMatrix.factory);
		testIncrement1(factory, SparseMatrix.factory);
		testIncrement2(factory, SparseMatrix.factory);
		testIncrement3(factory, SparseMatrix.factory);
		testIncrement4(factory, SparseMatrix.factory);
		testIncrement1(factory, DenseBySparseMatrix.factory);
		testIncrement2(factory, DenseBySparseMatrix.factory);
		testIncrement3(factory, DenseBySparseMatrix.factory);
		testIncrement4(factory, DenseBySparseMatrix.factory);
		testExceptions(factory);
		// Test exception thrown for dense matrix larger than largest possible (2147483647)
		try {
			Dictionary<String> d = getDictionary("d", 46341);
			assertEquals(46341, d.size());
			// This size is 2147488281
			factory.create(d, d);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
	}

	@Test
	public void testSparse() {
		MatrixFactory factory = SparseMatrix.factory;
		testBasic(factory);
		testIncrement1(factory, DenseMatrix.factory);
		testIncrement2(factory, DenseMatrix.factory);
		testIncrement3(factory, DenseMatrix.factory);
		testIncrement4(factory, DenseMatrix.factory);
		testIncrement1(factory, SparseMatrix.factory);
		testIncrement2(factory, SparseMatrix.factory);
		testIncrement3(factory, SparseMatrix.factory);
		testIncrement4(factory, SparseMatrix.factory);
		testIncrement1(factory, DenseBySparseMatrix.factory);
		testIncrement2(factory, DenseBySparseMatrix.factory);
		testIncrement3(factory, DenseBySparseMatrix.factory);
		testIncrement4(factory, DenseBySparseMatrix.factory);
		testExceptions(factory);

		// Test index conversions
		Set<Long> jointIndicesSeen = new HashSet<Long>();
		for (int row = 0; row < 100; row++) {
			for (int column = 0; column < 100; column++) {
				long jointIndex = SparseMatrix.getJointIndex(row, column);
				assertFalse(jointIndicesSeen.contains(jointIndex));
				assertEquals(row, SparseMatrix.getRow(jointIndex));
				assertEquals(column, SparseMatrix.getColumn(jointIndex));
				jointIndicesSeen.add(jointIndex);
				assertTrue(jointIndicesSeen.contains(jointIndex));
			}
		}
	}

	@Test
	public void testDenseBySparse() {
		MatrixFactory factory = DenseBySparseMatrix.factory;
		testBasic(factory);
		testIncrement1(factory, DenseMatrix.factory);
		testIncrement2(factory, DenseMatrix.factory);
		testIncrement3(factory, DenseMatrix.factory);
		testIncrement4(factory, DenseMatrix.factory);
		testIncrement1(factory, SparseMatrix.factory);
		testIncrement2(factory, SparseMatrix.factory);
		testIncrement3(factory, SparseMatrix.factory);
		testIncrement4(factory, SparseMatrix.factory);
		testIncrement1(factory, DenseBySparseMatrix.factory);
		testIncrement2(factory, DenseBySparseMatrix.factory);
		testIncrement3(factory, DenseBySparseMatrix.factory);
		testIncrement4(factory, DenseBySparseMatrix.factory);
		testExceptions(factory);
	}

	private static void testBasic(MatrixFactory factory) {

		Dictionary<String> rowDictionary = getDictionary("r", 4);
		Dictionary<String> columnDictionary = getDictionary("c", 2);

		Matrix<String, String> matrix = factory.create(rowDictionary, columnDictionary);

		assertEquals(4, matrix.numRows());
		assertEquals(2, matrix.numColumns());
		assertEquals(getDictionary("r", 4), matrix.getRowDictionary());
		assertEquals(getDictionary("c", 2), matrix.getColumnDictionary());

		assertEquals(0.0, matrix.get(0, 0), T1Constants.EPSILON);
		assertEquals(0.0, matrix.get(0, 1), T1Constants.EPSILON);
		assertEquals(0.0, matrix.get(1, 0), T1Constants.EPSILON);
		assertEquals(0.0, matrix.get(1, 1), T1Constants.EPSILON);
		assertEquals(0.0, matrix.get(2, 0), T1Constants.EPSILON);
		assertEquals(0.0, matrix.get(2, 1), T1Constants.EPSILON);
		assertEquals(0.0, matrix.get(3, 0), T1Constants.EPSILON);
		assertEquals(0.0, matrix.get(3, 1), T1Constants.EPSILON);

		matrix.set(0, 0, 0.35);
		// matrix.set(0, 1, 0.0);
		matrix.set(1, 0, 0.69);
		matrix.set(1, 1, 0.14);
		// matrix.set(2, 0, 0.0);
		matrix.set(2, 1, 0.81);

		assertEquals(0.35, matrix.get(0, 0), T1Constants.EPSILON);
		assertEquals(0.00, matrix.get(0, 1), T1Constants.EPSILON);
		assertEquals(0.69, matrix.get(1, 0), T1Constants.EPSILON);
		assertEquals(0.14, matrix.get(1, 1), T1Constants.EPSILON);
		assertEquals(0.00, matrix.get(2, 0), T1Constants.EPSILON);
		assertEquals(0.81, matrix.get(2, 1), T1Constants.EPSILON);
		assertEquals(0.00, matrix.get(3, 0), T1Constants.EPSILON);
		assertEquals(0.00, matrix.get(3, 1), T1Constants.EPSILON);

		matrix.set(0, 0, 0.54);
		matrix.set(0, 1, 0.66);
		matrix.set(1, 0, 0.20);
		matrix.set(1, 1, 0.42);
		matrix.set(2, 0, 0.53);
		matrix.set(2, 1, 0.99);

		assertEquals(0.54, matrix.get(0, 0), T1Constants.EPSILON);
		assertEquals(0.66, matrix.get(0, 1), T1Constants.EPSILON);
		assertEquals(0.20, matrix.get(1, 0), T1Constants.EPSILON);
		assertEquals(0.42, matrix.get(1, 1), T1Constants.EPSILON);
		assertEquals(0.53, matrix.get(2, 0), T1Constants.EPSILON);
		assertEquals(0.99, matrix.get(2, 1), T1Constants.EPSILON);
		assertEquals(0.00, matrix.get(3, 0), T1Constants.EPSILON);
		assertEquals(0.00, matrix.get(3, 1), T1Constants.EPSILON);

		assertEquals(4, matrix.numRows());
		assertEquals(2, matrix.numColumns());
		assertEquals(getDictionary("r", 4), matrix.getRowDictionary());
		assertEquals(getDictionary("c", 2), matrix.getColumnDictionary());

	}

	private static void testIncrement1(MatrixFactory factory1, MatrixFactory factory2) {
		Dictionary<String> rowDictionary = getDictionary("r", 3);
		Dictionary<String> columnDictionary = getDictionary("c", 3);

		Matrix<String, String> m1 = factory1.create(rowDictionary, columnDictionary);
		Matrix<String, String> m2 = factory2.create(rowDictionary, columnDictionary);

		m1.set(0, 0, 0.62);
		m1.set(0, 1, 0.26);
		m1.set(0, 2, 0.71);
		m1.set(2, 0, 0.21);
		m1.set(2, 1, 0.38);
		m1.set(2, 2, 0.75);

		m2.set(0, 0, 0.94);
		m2.set(0, 1, 0.99);
		m2.set(0, 2, 0.13);
		m2.set(1, 0, 0.60);
		m2.set(1, 1, 0.06);
		m2.set(1, 2, 0.79);

		m1.increment(m2);

		assertEquals(0.62 + 0.94, m1.get(0, 0), T1Constants.EPSILON);
		assertEquals(0.26 + 0.99, m1.get(0, 1), T1Constants.EPSILON);
		assertEquals(0.71 + 0.13, m1.get(0, 2), T1Constants.EPSILON);
		assertEquals(0.00 + 0.60, m1.get(1, 0), T1Constants.EPSILON);
		assertEquals(0.00 + 0.06, m1.get(1, 1), T1Constants.EPSILON);
		assertEquals(0.00 + 0.79, m1.get(1, 2), T1Constants.EPSILON);
		assertEquals(0.21 + 0.00, m1.get(2, 0), T1Constants.EPSILON);
		assertEquals(0.38 + 0.00, m1.get(2, 1), T1Constants.EPSILON);
		assertEquals(0.75 + 0.00, m1.get(2, 2), T1Constants.EPSILON);
	}

	private static void testIncrement2(MatrixFactory factory1, MatrixFactory factory2) {
		Dictionary<String> rowDictionary = getDictionary("r", 3);
		Dictionary<String> columnDictionary = getDictionary("c", 3);

		Matrix<String, String> m1 = factory1.create(rowDictionary, columnDictionary);
		Matrix<String, String> m2 = factory2.create(rowDictionary, columnDictionary);

		m1.set(0, 0, 0.61);
		m1.set(0, 1, 0.21);
		m1.set(0, 2, 0.33);
		m1.set(2, 0, 0.19);
		m1.set(2, 1, 0.17);
		m1.set(2, 2, 0.93);

		m2.set(0, 0, 0.28);
		m2.set(0, 1, 0.36);
		m2.set(0, 2, 0.90);
		m2.set(1, 0, 0.62);
		m2.set(1, 1, 0.34);
		m2.set(1, 2, 0.14);

		m1.increment(0.48, m2);

		assertEquals(0.61 + 0.48 * 0.28, m1.get(0, 0), T1Constants.EPSILON);
		assertEquals(0.21 + 0.48 * 0.36, m1.get(0, 1), T1Constants.EPSILON);
		assertEquals(0.33 + 0.48 * 0.90, m1.get(0, 2), T1Constants.EPSILON);
		assertEquals(0.00 + 0.48 * 0.62, m1.get(1, 0), T1Constants.EPSILON);
		assertEquals(0.00 + 0.48 * 0.34, m1.get(1, 1), T1Constants.EPSILON);
		assertEquals(0.00 + 0.48 * 0.14, m1.get(1, 2), T1Constants.EPSILON);
		assertEquals(0.19 + 0.48 * 0.00, m1.get(2, 0), T1Constants.EPSILON);
		assertEquals(0.17 + 0.48 * 0.00, m1.get(2, 1), T1Constants.EPSILON);
		assertEquals(0.93 + 0.48 * 0.00, m1.get(2, 2), T1Constants.EPSILON);
	}

	private static void testIncrement3(MatrixFactory factory1, MatrixFactory factory2) {
		Dictionary<String> rowDictionary = getDictionary("r", 2);
		Dictionary<String> columnDictionary = getDictionary("c", 3);

		Matrix<String, String> m1 = factory1.create(rowDictionary, columnDictionary);
		Matrix<String, String> m2 = factory2.create(rowDictionary, columnDictionary);

		m1.set(0, 0, 0.88);
		m1.set(0, 1, 0.68);
		m1.set(0, 2, 0.84);
		m1.set(1, 0, 0.45);
		m1.set(1, 1, 0.51);
		m1.set(1, 2, 0.21);

		m2.set(0, 0, 0.32);
		m2.set(0, 1, 0.49);
		m2.set(0, 2, 0.55);
		m2.set(1, 0, 0.92);
		m2.set(1, 1, 0.57);
		m2.set(1, 2, 0.62);

		m1.increment(m2);

		assertEquals(0.88 + 0.32, m1.get(0, 0), T1Constants.EPSILON);
		assertEquals(0.68 + 0.49, m1.get(0, 1), T1Constants.EPSILON);
		assertEquals(0.84 + 0.55, m1.get(0, 2), T1Constants.EPSILON);
		assertEquals(0.45 + 0.92, m1.get(1, 0), T1Constants.EPSILON);
		assertEquals(0.51 + 0.57, m1.get(1, 1), T1Constants.EPSILON);
		assertEquals(0.21 + 0.62, m1.get(1, 2), T1Constants.EPSILON);
	}

	private static void testIncrement4(MatrixFactory factory1, MatrixFactory factory2) {
		Dictionary<String> rowDictionary = getDictionary("r", 2);
		Dictionary<String> columnDictionary = getDictionary("c", 3);

		Matrix<String, String> m1 = factory1.create(rowDictionary, columnDictionary);
		Matrix<String, String> m2 = factory2.create(rowDictionary, columnDictionary);

		m1.set(0, 0, 0.88);
		m1.set(0, 1, 0.68);
		m1.set(0, 2, 0.84);
		m1.set(1, 0, 0.45);
		m1.set(1, 1, 0.51);
		m1.set(1, 2, 0.21);

		m2.set(0, 0, 0.32);
		m2.set(0, 1, 0.49);
		m2.set(0, 2, 0.55);
		m2.set(1, 0, 0.92);
		m2.set(1, 1, 0.57);
		m2.set(1, 2, 0.62);

		m1.increment(0.86, m2);

		assertEquals(0.88 + 0.86 * 0.32, m1.get(0, 0), T1Constants.EPSILON);
		assertEquals(0.68 + 0.86 * 0.49, m1.get(0, 1), T1Constants.EPSILON);
		assertEquals(0.84 + 0.86 * 0.55, m1.get(0, 2), T1Constants.EPSILON);
		assertEquals(0.45 + 0.86 * 0.92, m1.get(1, 0), T1Constants.EPSILON);
		assertEquals(0.51 + 0.86 * 0.57, m1.get(1, 1), T1Constants.EPSILON);
		assertEquals(0.21 + 0.86 * 0.62, m1.get(1, 2), T1Constants.EPSILON);
	}

	private static void testExceptions(MatrixFactory factory) {
		// Null dictionary
		Dictionary<String> rowDictionary = null;
		Dictionary<String> columnDictionary = getDictionary("c", 7);
		try {
			factory.create(rowDictionary, columnDictionary);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		rowDictionary = getDictionary("r", 5);
		columnDictionary = null;
		try {
			factory.create(rowDictionary, columnDictionary);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}

		// Dictionary not frozen
		rowDictionary = new Dictionary<String>();
		assertFalse(rowDictionary.isFrozen());
		columnDictionary = getDictionary("c", 7);
		try {
			factory.create(rowDictionary, columnDictionary);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		rowDictionary = getDictionary("r", 5);
		columnDictionary = new Dictionary<String>();
		assertFalse(columnDictionary.isFrozen());
		try {
			factory.create(rowDictionary, columnDictionary);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}

		rowDictionary = getDictionary("r", 5);
		columnDictionary = getDictionary("c", 7);
		Matrix<String, String> m = factory.create(rowDictionary, columnDictionary);
		assertEquals(5, m.numRows());
		assertEquals(7, m.numColumns());
		// Get index < 0
		try {
			m.get(-1, 3);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		try {
			m.get(3, -1);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		// Get index == size
		try {
			m.get(5, 2);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		try {
			m.get(2, 7);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		// Get index > size
		try {
			m.get(10, 4);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		try {
			m.get(4, 10);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		// Set index < 0
		try {
			m.set(-1, 3, 0.5);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		try {
			m.set(3, -1, 0.5);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		// Set index == size
		try {
			m.set(5, 2, 0.5);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		try {
			m.set(2, 7, 0.5);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		// Set index > size
		try {
			m.set(10, 4, 0.5);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		try {
			m.set(4, 10, 0.5);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		Matrix<String, String> m2 = factory.create(rowDictionary, getDictionary("c", 6));
		assertEquals(5, m2.numRows());
		assertEquals(6, m2.numColumns());
		try {
			m.increment(m2);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		try {
			m.increment(0.5, m2);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		Matrix<String, String> m3 = factory.create(getDictionary("r", 6), columnDictionary);
		assertEquals(6, m3.numRows());
		assertEquals(7, m3.numColumns());
		try {
			m.increment(m3);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		try {
			m.increment(0.5, m3);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
	}

	private static Dictionary<String> getDictionary(String prefix, int size) {
		Dictionary<String> dict = new Dictionary<String>();
		for (int i = 0; i < size; i++) {
			dict.addElement(prefix + i);
		}
		dict.freeze();
		return dict;
	}

}
