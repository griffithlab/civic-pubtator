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

public class file2sqlslit_rs2gene
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
			"(rs	CHAR(200)	NOT NULL, " + 
			" gene	CHAR(200)	NOT NULL )"; 
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
	public static void InsertRecord(String inputName,String DBName,String TableName) throws IOException, InterruptedException
	{
		Connection c = null;
		Statement stmt = null;
		Connection c_output = null;
		Statement stmt_output = null;
		try {
			Class.forName("org.sqlite.JDBC");
			c_output = DriverManager.getConnection("jdbc:sqlite:"+DBName);
			stmt_output = c_output.createStatement();
			
			c = DriverManager.getConnection("jdbc:sqlite:"+inputName);
			stmt = c.createStatement();
			String SQL="SELECT gene,rs FROM gene2rs";
			System.out.println(SQL);
			ResultSet rs = stmt.executeQuery(SQL);
			int count=0;
			String output_sql="INSERT INTO "+TableName+" VALUES";	
			while ( rs.next() ) 
			{
				String geneid=rs.getString("gene");
				String rsids_arr[]=rs.getString("rs").split("\\|");
				for(int x=0;x<rsids_arr.length;x++)
				{
					if(count%1000==0)
					{
						output_sql=output_sql+"('"+rsids_arr[x]+"','"+geneid+"');";
						stmt_output.executeUpdate(output_sql);
						output_sql="INSERT INTO "+TableName+" VALUES";	
						System.out.println(count);
					}
					else
					{
						output_sql=output_sql+"('"+rsids_arr[x]+"','"+geneid+"'),";
					}
					count++;
				}
			}
			stmt_output.close();
			c_output.close();
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
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit_merged.jar CreateTable [DatabaseName] [TableName]");
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit_merged.jar CreateTable Database/RegularlyUpdate/rs2gene.db rs2gene");
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit_merged.jar InsertRecord Database/RegularlyUpdate/rs2gene.txt Database/RegularlyUpdate/rs2gene.db rs2gene\n");
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit_merged.jar Indexing Database/RegularlyUpdate/rs2gene.db rs2gene origin\n");
			
			System.out.println("CreateTable");
			CreateTable("Database/RegularlyUpdate/rs2gene.db","rs2gene");
			
			System.out.println("InsertRecord");
			InsertRecord("Database/RegularlyUpdate/gene2rs.db","Database/RegularlyUpdate/rs2gene.db","rs2gene");

			System.out.println("Indexing");
			Indexing("Database/RegularlyUpdate/rs2gene.db","rs2gene","rs");
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
