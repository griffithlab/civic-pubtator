package db;
//
// https://bitbucket.org/xerial/sqlite-jdbc/downloads --> sqlite-jdbc-3.8.11.2.jar
// Add to build path
//

import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.sql.*;
import java.util.HashMap;
import java.util.List;

public class file2sqlslit_prefix
{
	public static void CreateTable(String DBName,String TableName) throws IOException, InterruptedException
	{
		Connection c = null;
		Statement stmt = null;
		try {
			Class.forName("org.sqlite.JDBC");
			
			c = DriverManager.getConnection("jdbc:sqlite:Database/RegularlyUpdate/"+DBName+".db");
			stmt = c.createStatement();
			String sql = "CREATE TABLE "+TableName+" " +
			"(var	CHAR(200)	NOT NULL, " + 
			" rs	TEXT	NOT NULL )"; 
			stmt.executeUpdate(sql);
			stmt.close();
			c.close();
		} 
		catch ( Exception e ) 
		{
			System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			System.exit(0);
		}

	}
	public static void CreateTable_gene2rs(String DBName,String TableName) throws IOException, InterruptedException
	{
		Connection c = null;
		Statement stmt = null;
		try {
			Class.forName("org.sqlite.JDBC");
			
			c = DriverManager.getConnection("jdbc:sqlite:Database/RegularlyUpdate/"+DBName+".db");
			stmt = c.createStatement();
			String sql = "CREATE TABLE "+TableName+" " +
					"(gene	CHAR(200)	NOT NULL, " + 
					" rs	TEXT	NOT NULL )"; 
			stmt.executeUpdate(sql);
			stmt.close();
			c.close();
		} 
		catch ( Exception e ) 
		{
			System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			System.exit(0);
		}

	}
	
	public static void Indexing(String DBName,String TableName,String index) throws IOException, InterruptedException
	{
		Connection c = null;
		Statement stmt = null;
		try {
			Class.forName("org.sqlite.JDBC");
			
			try {
				c = DriverManager.getConnection("jdbc:sqlite:Database/RegularlyUpdate/"+DBName+".db");
				stmt = c.createStatement();
				stmt.executeUpdate("CREATE INDEX "+TableName+"_index ON "+TableName+" ("+index+")");
				stmt.close();
				c.close();
			} 
			catch ( SQLException e ) 
			{
				System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			}
			
			/*
			try {
				c = DriverManager.getConnection("jdbc:sqlite:Database/var2rs_c.db");
				stmt = c.createStatement();
				stmt.executeUpdate("CREATE INDEX var2rs_c_index ON var2rs_c (var)");
				stmt.close();
				c.close();
			} 
			catch ( SQLException e ) 
			{
				System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			}
			
			try {
				c = DriverManager.getConnection("jdbc:sqlite:Database/var2rs_g.db");
				stmt = c.createStatement();
				stmt.executeUpdate("CREATE INDEX var2rs_g_index ON var2rs_g (var)");
				stmt.close();
				c.close();
			} 
			catch ( SQLException e ) 
			{
				System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			}
			
			try {
				c = DriverManager.getConnection("jdbc:sqlite:Database/var2rs_m.db");
				stmt = c.createStatement();
				stmt.executeUpdate("CREATE INDEX var2rs_m_index ON var2rs_m (var)");
				stmt.close();
				c.close();
			} 
			catch ( SQLException e ) 
			{
				System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			}
			
			try {
				c = DriverManager.getConnection("jdbc:sqlite:Database/var2rs_n.db");
				stmt = c.createStatement();
				stmt.executeUpdate("CREATE INDEX var2rs_n_index ON var2rs_n (var)");
				stmt.close();
				c.close();
			} 
			catch ( SQLException e ) 
			{
				System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			}
			
			try {
				c = DriverManager.getConnection("jdbc:sqlite:Database/var2rs_p.db");
				stmt = c.createStatement();
				stmt.executeUpdate("CREATE INDEX var2rs_n_index ON var2rs_p (var)");
				stmt.close();
				c.close();
			} 
			catch ( SQLException e ) 
			{
				System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			}
			
			
			try {
				c = DriverManager.getConnection("jdbc:sqlite:Database/var2rs_clinvar.db");
				stmt = c.createStatement();
				stmt.executeUpdate("CREATE INDEX var2rs_clinvar_index ON var2rs_clinvar (var)");
				stmt.close();
				c.close();
			} 
			catch ( SQLException e ) 
			{
				System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			}
			
					
			try {
				c = DriverManager.getConnection("jdbc:sqlite:Database/gene2rs.db");
				stmt = c.createStatement();
				stmt.executeUpdate("CREATE INDEX gene2rs_index ON gene2rs (gene)");
				stmt.close();
				c.close();
			} 
			catch ( SQLException e ) 
			{
				System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			}
			*/
		} 
		catch ( Exception e ) 
		{
			System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			System.exit(0);
		}

	}
	public static void InsertRecord(String FileName,String DBName,String TableName) throws IOException, InterruptedException
	{
		Connection c = null;
		Statement stmt = null;
		try {
			Class.forName("org.sqlite.JDBC");
			c = DriverManager.getConnection("jdbc:sqlite:Database/RegularlyUpdate/"+DBName+".db");
			stmt = c.createStatement();
			
			BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(FileName), "UTF-8"));
			String line="";
			String sql="INSERT INTO "+TableName+" VALUES";
			int count=0;
			while ((line = br.readLine()) != null)  
			{
				String nt[]=line.split("\t");
				if(count%1000==0)
				{
					sql=sql+"('"+nt[0]+"','"+nt[1]+"');";
					stmt.executeUpdate(sql);
					sql="INSERT INTO "+TableName+" VALUES";	   
				}
				else
				{
					sql=sql+"('"+nt[0]+"','"+nt[1]+"'),";
				}
				count++;
			}
			br.close();
			
			stmt.close();
			c.close();
		} 
		catch ( Exception e ) 
		{
			System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			System.exit(0);
		}
	}
	public static void InsertRecord_gene2rs(String FileName,String DBName,String TableName) throws IOException, InterruptedException
	{
		Connection c = null;
		Statement stmt = null;
		try {
			Class.forName("org.sqlite.JDBC");
			c = DriverManager.getConnection("jdbc:sqlite:Database/RegularlyUpdate/"+DBName+".db");
			stmt = c.createStatement();
			
			BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(FileName), "UTF-8"));
			String line="";
			while ((line = br.readLine()) != null)  
			{
				String nt[]=line.split("\t");
				String sql="insert into "+TableName+" values('"+nt[0]+"','"+nt[1]+"')";
				stmt.executeUpdate(sql);
			}
			br.close();
			
			stmt.close();
			c.close();
		} 
		catch ( Exception e ) 
		{
			System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			System.exit(0);
		}
	}
	public static void main(String [] args) throws IOException, InterruptedException, SQLException, ClassNotFoundException 
	{
		if(args.length<3)
		{
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit.jar CreateTable [DatabaseName] [TableName]");
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit.jar CreateTable var2rs_c var2rs_c");
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit.jar CreateTable_gene2rs gene2rs gene2rs\n");
			
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit.jar Indexing [DatabaseName] [TableName] [Index]");
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit.jar Indexing var2rs_g var2rs_g var\n");
			
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit.jar InsertRecord [InputFile] [DatabaseName] [TableName]");
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit.jar InsertRecord var2rs_c.txt var2rs_c\n");
			
			System.out.println("CreateTable");
			CreateTable("var2rs_Xc","var2rs_c");
			CreateTable("var2rs_Xg","var2rs_g");
			CreateTable("var2rs_Xm","var2rs_m");
			CreateTable("var2rs_Xn","var2rs_n");
			CreateTable("var2rs_Xp","var2rs_p");
			
			System.out.println("InsertRecord");
			InsertRecord("Database/var2rs.p.X.txt","var2rs_Xp","var2rs_p");
			InsertRecord("Database/var2rs.c.X.txt","var2rs_Xc","var2rs_c");
			InsertRecord("Database/var2rs.g.X.txt","var2rs_Xg","var2rs_g");
			InsertRecord("Database/var2rs.m.X.txt","var2rs_Xm","var2rs_m");
			InsertRecord("Database/var2rs.n.X.txt","var2rs_Xn","var2rs_n");
			
			System.out.println("Indexing");
			Indexing("var2rs_Xp","var2rs_p","var");
			Indexing("var2rs_Xc","var2rs_c","var");
			Indexing("var2rs_Xg","var2rs_g","var");
			Indexing("var2rs_Xm","var2rs_m","var");
			Indexing("var2rs_Xn","var2rs_n","var");
			
		}
		else if (args[0].equals("CreateTable"))
		{
			String db= args[1];
			String table = args[2];
			CreateTable(db,table);
		}
		else if (args[0].equals("CreateTable_gene2rs"))
		{
			String db= args[1];
			String table = args[2];
			CreateTable_gene2rs(db,table);
		}
		else if (args[0].equals("Indexing"))
		{
			/*
			 * var2rs --> var
			 * gene2rs --> gene
			 */
			String db= args[1];
			String table = args[2];
			String index = args[3];
			System.out.println("Indexing: "+db+"\t"+table+"\t"+index);
			Indexing(db,table,index);
		}
		else if (args[0].equals("InsertRecord"))
		{
			String file= args[1];
			String db = args[2];
			String table = args[3];
			System.out.println(file+"\t"+db+"\t"+table);
	
			if(table.equals("gene2rs"))
			{
				InsertRecord_gene2rs(file,db,table);
			}
			else
			{
				InsertRecord(file,db,table);
			}
		}
		
	}
}
