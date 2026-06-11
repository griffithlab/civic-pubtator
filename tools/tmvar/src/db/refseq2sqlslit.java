package db;
//
// https://bitbucket.org/xerial/sqlite-jdbc/downloads --> sqlite-jdbc-3.8.11.2.jar
// Add to build path
//

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.FileReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.sql.*;
import java.util.HashMap;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;

public class refseq2sqlslit
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
			"(geneid	CHAR(200)	NOT NULL, " + 
			"seqid	CHAR(200)	NOT NULL, " + 
			"gi	CHAR(200)	NOT NULL, " + 
			"type	CHAR(200)	NOT NULL, " + 
			"seq	TEXT	NOT NULL )"; 
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
	public static void ExtractSeq(String FileName,String OutputFileName) throws MalformedURLException, IOException, InterruptedException
	{
		try {
			BufferedWriter bw = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(OutputFileName), "UTF-8"));
			BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(FileName), "UTF-8"));
			String line="";
			while ((line = br.readLine()) != null)  
			{
				String nt[]=line.split("\t");
				//9606	1	REVIEWED	NM_130786.3	161377438	NP_570602.2	21071030
				if(nt[0].equals("9606"))
				{
					String geneid=nt[1];
					//DNA Sequence
					String seqid=nt[3];
					String gi=nt[4];
					if(!seqid.equals("-"))
					{
						URL query = new URL("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=protein&retmode=text&rettype=fasta&id="+seqid);
						HttpURLConnection conn_Submit = (HttpURLConnection) query.openConnection();
						conn_Submit.setDoOutput(true);
						BufferedReader br_query = new BufferedReader(new InputStreamReader(conn_Submit.getInputStream()));
						String fastaSeq="";
						String Seq="";
						while((fastaSeq = br_query.readLine()) != null)
						{
							if(fastaSeq.length()>1 && !fastaSeq.substring(0, 1).equals(">"))
							{
								Seq=Seq+fastaSeq;
							}
						}
						conn_Submit.disconnect();
						Seq=Seq.replaceAll("\n", "");
						String type="DNA";
						bw.write(geneid+"\t"+seqid+"\t"+gi+"\t"+type+"\t"+Seq+"\n");
						Thread.sleep(1000);
					}	
					//Protein Sequence
					seqid=nt[5];
					gi=nt[6];
					if(!seqid.equals("-"))
					{
						URL query = new URL("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=protein&retmode=text&rettype=fasta&id="+seqid);
						HttpURLConnection conn_Submit = (HttpURLConnection) query.openConnection();
						conn_Submit.setDoOutput(true);
						BufferedReader br_query = new BufferedReader(new InputStreamReader(conn_Submit.getInputStream()));
						String fastaSeq="";
						String Seq="";
						while((fastaSeq = br_query.readLine()) != null)
						{
							if(fastaSeq.length()>1 && !fastaSeq.substring(0, 1).equals(">"))
							{
								Seq=Seq+fastaSeq;
							}
						}
						conn_Submit.disconnect();
						Seq=Seq.replaceAll("\n", "");
						String type="Protein";
						bw.write(geneid+"\t"+seqid+"\t"+gi+"\t"+type+"\t"+Seq+"\n");
						Thread.sleep(1000);
					}
				}
			}
			br.close();
			bw.close();
		}
		catch ( Exception e ) 
		{
			System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			System.exit(0);
		}
	}
	public static void ExtractSeq_Ayush(String OutputFileName) throws MalformedURLException, IOException, InterruptedException
	{
		try {
			BufferedWriter bw = new BufferedWriter(new OutputStreamWriter(new FileOutputStream(OutputFileName), "UTF-8"));
			
			BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream("Database/RegularlyUpdate/refseq/refseq.Sequence.txt"), "UTF-8"));
			HashMap<String,String> seqid_exists = new HashMap<String,String>();
			String line="";
			while ((line = br.readLine()) != null)  
			{
				//449520	XM_001724454.1	169169538	DNA	GGCTGCTCCTC
				String nt[]=line.split("\t");
				String geneid=nt[0];
				String seqid=nt[1];
				seqid_exists.put(seqid, geneid);
			}
			br.close();
			br = new BufferedReader(new InputStreamReader(new FileInputStream("Database/RegularlyUpdate/refseq/NCBI_gene_protein_map_full2.p"), "UTF-8"));
			line="";
			HashMap<String,String> seqid2geneid = new HashMap<String,String>();
			while ((line = br.readLine()) != null)  
			{
				//221545	NP_001103408.1,NP_001154848.1,NP_659466.2
				String nt[]=line.split("\t");
				String geneid=nt[0];
				String seqid[]=nt[1].split(",");
				for(int i=0;i<seqid.length;i++)
				{
					seqid2geneid.put(seqid[i], geneid);
				}
			}
			br.close();
			br = new BufferedReader(new InputStreamReader(new FileInputStream("Database/RegularlyUpdate/refseq/NCBI_protein_FASTA.p"), "UTF-8"));
			line="";
			while ((line = br.readLine()) != null)  
			{
				//NP_001295087.1	MFKIGRGALDLFSELLSFG
				String nt[]=line.split("\t");
				String seqid=nt[0];
				String Seq=nt[1];
				String geneid="";
				if(seqid2geneid.containsKey(seqid))
				{
					geneid=seqid2geneid.get(seqid);
				}
				else
				{
					URL query = new URL("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=protein&retmode=xml&id="+seqid);
					HttpURLConnection conn_Submit = (HttpURLConnection) query.openConnection();
					conn_Submit.setDoOutput(true);
					BufferedReader br_query = new BufferedReader(new InputStreamReader(conn_Submit.getInputStream()));
					while((line = br_query.readLine()) != null)
					{
						Pattern pat = Pattern.compile("GeneID:([0-9]+)");
						Matcher mat = pat.matcher(line);
						if(mat.find()) //Title|Abstract
						{
							geneid=mat.group(1);
							seqid2geneid.put(seqid,geneid);
							System.out.println(seqid+"\t"+geneid);
							break;
						}
					}
					Thread.sleep(1000);
					conn_Submit.disconnect();
				}
				if(!seqid_exists.containsKey(seqid))
				{
					bw.write(geneid+"\t"+seqid+"\t-\tProtein\t"+Seq+"\n");
				}
			}
			br.close();
			
			br = new BufferedReader(new InputStreamReader(new FileInputStream("Database/RegularlyUpdate/refseq/GenSeq_FASTA.p"), "UTF-8"));
			line="";
			while ((line = br.readLine()) != null)  
			{
				//NP_001295087.1	MFKIGRGALDLFSELLSFG
				String nt[]=line.split("\t");
				String geneid=nt[0];
				String Seq=nt[1];
				bw.write(geneid+"\t-\t-\tDNA\t"+Seq+"\n");
			}
			br.close();
			
			bw.close();
		}
		catch ( Exception e ) 
		{
			System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			System.exit(0);
		}
	}
	public static void InsertRecord(String FileName,String DBName,String TableName) throws MalformedURLException, IOException, InterruptedException
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
				String nt[]=line.split("\t",-1);
				//1	NM_130786.3	161377438	DNA	GGGCCTCATTGCTGCAGACGCT
				String geneid=nt[0];
				String seqid=nt[1];
				String gi=nt[2];
				String type=nt[3];
				String Seq=nt[4];
				String insertion_sql="INSERT INTO "+TableName+" VALUES('"+geneid+"','"+seqid+"','"+gi+"','"+type+"','"+Seq+"');";
				stmt.executeUpdate(insertion_sql);
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
			
		} 
		catch ( Exception e ) 
		{
			System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			System.exit(0);
		}

	}
	public static void Search(String DBName,String TableName,String SearchColumn,String Searchid) throws IOException, InterruptedException, SQLException
	{
		Connection c = null;
		Statement stmt = null;
		try {
			Class.forName("org.sqlite.JDBC");
		} 
		catch ( Exception e ) 
		{
			System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			System.exit(0);
		}
		c = DriverManager.getConnection("jdbc:sqlite:Database/RegularlyUpdate/"+DBName+".db");
		stmt = c.createStatement();
		String SQL="SELECT * FROM "+TableName+" WHERE "+SearchColumn+"='"+Searchid+"' and type='DNA'";
		System.out.println(SQL);
		ResultSet data = stmt.executeQuery(SQL);
		while ( data.next() ) 
		{
			System.out.println(data.getString("geneid")+"\t"+data.getString("seqid")+"\t"+data.getString("gi")+"\t"+data.getString("type")+"\t"+data.getString("Seq"));
		}
		stmt.close();
		c.close();
	}
	public static void main(String [] args) throws IOException, InterruptedException, SQLException, ClassNotFoundException 
	{
		if(args.length<3)
		{
			System.out.println("$ java -Xmx5G -Xms5G -jar refseq2sqlslit.jar CreateTable [DatabaseName] [TableName]");
			System.out.println("$ java -Xmx5G -Xms5G -jar refseq2sqlslit.jar Indexing [DatabaseName] [TableName] [Index]");
			System.out.println("$ java -Xmx5G -Xms5G -jar refseq2sqlslit.jar InsertRecord [InputFile] [DatabaseName] [TableName]");
			System.out.println("$ java -Xmx5G -Xms5G -jar refseq2sqlslit.jar Search [InputFile] [DatabaseName] [SearchColumn:geneid|seqid|gi|type] [id]");
			
			System.out.println("ExtractSeq");
			ExtractSeq("Database/RegularlyUpdate/refseq/refseq.txt","Database/RegularlyUpdate/refseq/refseq.Sequence.txt");
			
			//System.out.println("ExtractSeq_Ayush");
			//ExtractSeq_Ayush("Database/RegularlyUpdate/refseq/Ayush.refseq.Sequence.txt");
			
			//System.out.println("CreateTable");
			//CreateTable("refseq","refseq");
			
			//System.out.println("InsertRecord");
			//InsertRecord("Database/RegularlyUpdate/refseq/refseq.Sequence.txt","refseq","refseq");
			//InsertRecord("Database/RegularlyUpdate/refseq/Ayush.refseq.Sequence.txt","refseq","refseq");
			
			//System.out.println("Indexing");
			//Indexing("refseq","refseq","geneid");
			//Indexing("refseq","refseq","seqid");
			//Indexing("refseq","refseq","gi");
			//Indexing("refseq","refseq","type");
			
			//Search("refseq","refseq","geneid","2099");
		}
		else if (args[0].equals("CreateTable"))
		{
			String db= args[1];
			String table = args[2];
			CreateTable(db,table);
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
	
			InsertRecord(file,db,table);
		}
		else if (args[0].equals("Search"))
		{
			String db= args[1];
			String table = args[2];
			String SearchColumn = args[3];
			String Searchid = args[4];
			Search(db,table,SearchColumn,Searchid);
		}
	}
}
