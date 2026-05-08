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

public class file2sqlslit_gene2sp
{
	public static void CreateTable(String DBName,String TableName) throws IOException, InterruptedException
	{
		Connection c = null;
		Statement stmt = null;
		try {
			Class.forName("org.sqlite.JDBC");
			
			c = DriverManager.getConnection("jdbc:sqlite:"+DBName);
			stmt = c.createStatement();
			String sql = "CREATE TABLE "+TableName+" " +
			"(gene	CHAR(200)	NOT NULL, " + 
			" tax	CHAR(200)	NOT NULL )"; 
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
				c = DriverManager.getConnection("jdbc:sqlite:"+DBName);
				stmt = c.createStatement();
				stmt.executeUpdate("CREATE INDEX "+TableName+"_index ON "+TableName+" ("+index+")");
				stmt.close();
				c.close();
			} 
			catch ( SQLException e ) 
			{
				System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			}
			
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
			c = DriverManager.getConnection("jdbc:sqlite:"+DBName);
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
					sql=sql+"('"+nt[1]+"','"+nt[0]+"');";
					stmt.executeUpdate(sql);
					sql="INSERT INTO "+TableName+" VALUES";	   
				}
				else
				{
					sql=sql+"('"+nt[1]+"','"+nt[0]+"'),";
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
	public static void main(String [] args) throws IOException, InterruptedException, SQLException, ClassNotFoundException 
	{
		if(args.length<3)
		{
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit_gene2tax.jar CreateTable [DatabaseName] [TableName]");
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit_gene2tax.jar CreateTable Database/RegularlyUpdate/gene2tax.db rs2gene");
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit_gene2tax.jar InsertRecord Database/RegularlyUpdate/gene2tax.txt Database/RegularlyUpdate/gene2tax.db rs2gene\n");
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit_gene2tax.jar Indexing Database/RegularlyUpdate/gene2tax.db rs2gene origin\n");
			
			System.out.println("CreateTable");
			CreateTable("Database/RegularlyUpdate/gene2tax.db","gene2tax");
			
			System.out.println("InsertRecord");
			InsertRecord("Database/RegularlyUpdate/gene_info/gene_info","Database/RegularlyUpdate/gene2tax.db","gene2tax");

			System.out.println("Indexing");
			Indexing("Database/RegularlyUpdate/gene2tax.db","gene2tax","gene");
		}
		else if (args[0].equals("CreateTable"))
		{
			String db= args[1];
			String table = args[2];
			CreateTable(db,table);
		}
		else if (args[0].equals("InsertRecord"))
		{
			String file = args[1];
			String db = args[2];
			String table = args[3];
			InsertRecord(file,db,table);
		}
		else if (args[0].equals("Indexing"))
		{
			String db= args[1];
			String table = args[2];
			String index = args[3];
			System.out.println("Indexing: "+db+"\t"+table+"\t"+index);
			Indexing(db,table,index);
		}
	}
}
